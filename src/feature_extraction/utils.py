import numpy as np


def refine(boxes, max_width, max_height, shift=0.1):
    """调整人脸框，使其更适合后续关键点检测。

    参数：
        boxes: [[x1, y1, x2, y2], ...]
        max_width: 超出该值的部分会被裁剪。
        max_height: 超出该值的部分会被裁剪。
        shift (float, optional): 人脸框向下偏移的比例，默认 0.1。

    返回：
       调整后的结果。
    """
    refined = boxes.copy()
    width = refined[:, 2] - refined[:, 0]
    height = refined[:, 3] - refined[:, 1]

    # 在 Y 方向上移动人脸框
    shift = height * shift
    refined[:, 1] += shift
    refined[:, 3] += shift
    center_x = (refined[:, 0] + refined[:, 2]) / 2
    center_y = (refined[:, 1] + refined[:, 3]) / 2

    # 将人脸框调整为正方形
    square_sizes = np.maximum(width, height)
    refined[:, 0] = center_x - square_sizes / 2
    refined[:, 1] = center_y - square_sizes / 2
    refined[:, 2] = center_x + square_sizes / 2
    refined[:, 3] = center_y + square_sizes / 2

    # 为了安全起见，对边界做裁剪
    refined[:, 0] = np.clip(refined[:, 0], 0, max_width)
    refined[:, 1] = np.clip(refined[:, 1], 0, max_height)
    refined[:, 2] = np.clip(refined[:, 2], 0, max_width)
    refined[:, 3] = np.clip(refined[:, 3], 0, max_height)

    return refined
