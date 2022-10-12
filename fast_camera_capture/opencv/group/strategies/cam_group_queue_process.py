import math
import multiprocessing
from multiprocessing import Process
from time import perf_counter_ns, sleep
from typing import Dict, List

from setproctitle import setproctitle

from fast_camera_capture import CamArgs, Camera
from fast_camera_capture.detection.models.frame_payload import FramePayload
from fast_camera_capture.opencv.group.strategies.queue_communicator import QueueCommunicator


class CamGroupProcess:
    def __init__(self, cam_ids: List[str]):
        self._cam_ids = cam_ids
        self._process: Process = None
        self._payload = None
        communicator = QueueCommunicator(cam_ids)
        self._queues = communicator.queues

    @property
    def camera_ids(self):
        return self._cam_ids

    def start_capture(self):
        """
        Start capturing frames. Only return if the underlying process is fully running.
        :return:
        """
        self._process = Process(
            name=f"Cameras {self._cam_ids}",
            target=CamGroupProcess._begin,
            args=(self._cam_ids, self._queues)
        )
        self._process.start()
        while not self._process.is_alive():
            sleep(1)

    @property
    def is_capturing(self):
        if self._process:
            return self._process.is_alive()
        return False

    @staticmethod
    def _create_cams(cam_ids: List[str]):
        return [Camera(CamArgs(cam_id=cam)) for cam in cam_ids]

    @staticmethod
    def _begin(cam_ids: List[str], queues: Dict[str, multiprocessing.Queue]):
        setproctitle(f"Cameras {cam_ids}")
        cameras = CamGroupProcess._create_cams(cam_ids)
        for cam in cameras:
            cam.connect()
        while True:
            # This tight loop ends up 100% the process, so a sleep between framecaptures is
            # necessary. We can get away with this because we don't expect another frame for
            # awhile.
            sleep(0.05)
            for cam in cameras:
                if cam.new_frame_ready:
                    queue = queues[cam.cam_id]
                    queue.put(cam.latest_frame)

    def get_by_cam_id(self, cam_id) -> FramePayload | None:
        if cam_id not in self._queues:
            return

        queue = self._queues[cam_id]
        if not queue.empty():
            return queue.get(block=True)


if __name__ == "__main__":
    p = CamGroupProcess(["0"])
    p.start_capture()
    while True:
        # print("Queue size: ", p.queue_size("0"))
        curr = perf_counter_ns() * 1e-6
        frames = p.get_by_cam_id("0")
        if frames:
            end = perf_counter_ns() * 1e-6
            frame_count_in_ms = f"{math.trunc(end - curr)}"
            print(f"{frame_count_in_ms}ms for this frame")