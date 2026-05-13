import numpy as np
from io_interface import IOInterface


def send_to_scoring(o):
    import json
    print("OUTPUT_JSON_START")
    print(json.dumps(o, indent=2, ensure_ascii=False))
    print("OUTPUT_JSON_END")
    global last_output
    last_output = o


class MockMark:
    def detect(self, images):
        return np.zeros((1, 136), dtype=np.float32)


class MockPose:
    def solve(self, marks):
        return np.zeros((3, 1)), np.zeros((3, 1))

    def get_head_pose_data(self, marks, pose=None):
        return {'head_pose': {'pitch': 1.0, 'yaw': 2.0, 'roll': 3.0, 'confidence': 0.9}}


class MockFace:
    pass


io = IOInterface.__new__(IOInterface)
io.mark_detector = MockMark()
io.face_detector = MockFace()
io.pose_estimator = MockPose()
io.pose_estimator.size = (480, 640)

frame = np.zeros((480, 640, 3), dtype=np.uint8)
face_roi = np.zeros((200, 200, 3), dtype=np.uint8)
record = {'timestamp': 123.456, 'faces': [{'face_id': 1, 'face_roi': face_roi}], 'owner_face_id': 1, 'frame': frame}

io.process(record, send_to_scoring)

import sys
try:
    o = last_output
except NameError:
    sys.exit(1)

print('FIELDS:', sorted(list(o.keys())))
print('FEATURES_KEYS:', sorted(list(o['features'].keys())))
