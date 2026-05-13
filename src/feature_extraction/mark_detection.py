import os

import cv2
import numpy as np
import onnxruntime as ort


class MarkDetector:
    """基于卷积神经网络的人脸关键点检测器。"""

    def __init__(self, model_file):
        """初始化关键点检测器。

        参数：
            model_file (str): ONNX 模型路径。
        """
        assert os.path.exists(model_file), f"File not found: {model_file}"
        self._input_size = 128
        self.model = ort.InferenceSession(
            model_file, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

    def _preprocess(self, bgrs):
        """对输入图像做预处理，使其满足模型要求。

        参数：
            bgrs (np.ndarray): BGR 格式的输入图像列表。

        返回：
            tf.Tensor: 张量数据。
        """
        rgbs = []
        for img in bgrs:
            img = cv2.resize(img, (self._input_size, self._input_size))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            rgbs.append(img)

        return rgbs

    def detect(self, images):
        """从人脸图像中检测面部关键点。

        参数：
            images: 人脸图像列表。

        Returns:
            marks: 形状为 [Batch, 68*2] 的关键点数组。
        """
        inputs = self._preprocess(images)
        marks = self.model.run(["dense_1"], {"image_input": inputs})
        return np.array(marks)

    def visualize(self, image, marks, color=(255, 255, 255)):
        """在图像上绘制关键点。"""
        for mark in marks:
            cv2.circle(image, (int(mark[0]), int(
                mark[1])), 1, color, -1, cv2.LINE_AA)
