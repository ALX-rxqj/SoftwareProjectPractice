import cv2
import numpy as np


class PoseEstimator:
    """根据人脸关键点估计头部姿态。"""

    def __init__(self, image_width, image_height):
        """初始化姿态估计器。

        参数：
            image_width (int): 输入图像宽度
            image_height (int): 输入图像高度
        """
        self.size = (image_height, image_width)
        self.model_points_68 = self._get_full_model_points()

        # 相机内参
        self.focal_length = self.size[1]
        self.camera_center = (self.size[1] / 2, self.size[0] / 2)
        self.camera_matrix = np.array(
            [[self.focal_length, 0, self.camera_center[0]],
             [0, self.focal_length, self.camera_center[1]],
             [0, 0, 1]], dtype="double")

        # 假设没有镜头畸变
        self.dist_coeefs = np.zeros((4, 1))

        # 旋转向量和位移向量
        self.r_vec = np.array([[0.01891013], [0.08560084], [-3.14392813]])
        self.t_vec = np.array(
            [[-14.97821226], [-10.62040383], [-2053.03596872]])

    def _get_full_model_points(self, filename='assets/model.txt'):
        """从文件中读取全部 68 个三维模型点。"""
        raw_value = []
        with open(filename) as file:
            for line in file:
                raw_value.append(line)
        model_points = np.array(raw_value, dtype=np.float32)
        model_points = np.reshape(model_points, (3, -1)).T

        # 将模型转换为正视方向。
        model_points[:, 2] *= -1

        return model_points

    def solve(self, points):
        """使用全部 68 个图像点求解姿态。
        参数：
            points (np.ndarray): 图像上的关键点。

        返回：
            Tuple: 作为姿态结果返回的 (rotation_vector, translation_vector)。
        """

        if self.r_vec is None:
            (_, rotation_vector, translation_vector) = cv2.solvePnP(
                self.model_points_68, points, self.camera_matrix, self.dist_coeefs)
            self.r_vec = rotation_vector
            self.t_vec = translation_vector

        (_, rotation_vector, translation_vector) = cv2.solvePnP(
            self.model_points_68,
            points,
            self.camera_matrix,
            self.dist_coeefs,
            rvec=self.r_vec,
            tvec=self.t_vec,
            useExtrinsicGuess=True)

        return (rotation_vector, translation_vector)

    @staticmethod
    def _rotation_matrix_to_euler(rotation_matrix):
        """将旋转矩阵转换为欧拉角（单位：度）。"""
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
        singular = sy < 1e-6

        if not singular:
            pitch = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            yaw = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            pitch = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            yaw = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = 0

        return np.degrees([pitch, yaw, roll])

    def get_head_pose_data(self, points, pose=None):
        """构建结构化的头部姿态输出，置信度范围为 0 到 1。"""
        if pose is None:
            pose = self.solve(points)

        rotation_vector, translation_vector = pose
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        pitch, yaw, roll = self._rotation_matrix_to_euler(rotation_matrix)

        # 使用平均重投影误差作为简单的置信度代理。
        projected, _ = cv2.projectPoints(
            self.model_points_68,
            rotation_vector,
            translation_vector,
            self.camera_matrix,
            self.dist_coeefs)
        projected = projected.reshape(-1, 2)
        reprojection_error = np.mean(np.linalg.norm(points - projected, axis=1))
        confidence = float(np.clip(np.exp(-reprojection_error / 20.0), 0.0, 1.0))

        return {
            "head_pose": {
                "pitch": float(pitch),
                "yaw": float(yaw),
                "roll": float(roll),
                "confidence": confidence
            }
        }

    def visualize(self, image, pose, color=(255, 255, 255), line_width=2):
        """绘制一个 3D 盒子作为姿态标注。"""
        rotation_vector, translation_vector = pose
        point_3d = []
        rear_size = 75
        rear_depth = 0
        point_3d.append((-rear_size, -rear_size, rear_depth))
        point_3d.append((-rear_size, rear_size, rear_depth))
        point_3d.append((rear_size, rear_size, rear_depth))
        point_3d.append((rear_size, -rear_size, rear_depth))
        point_3d.append((-rear_size, -rear_size, rear_depth))

        front_size = 100
        front_depth = 100
        point_3d.append((-front_size, -front_size, front_depth))
        point_3d.append((-front_size, front_size, front_depth))
        point_3d.append((front_size, front_size, front_depth))
        point_3d.append((front_size, -front_size, front_depth))
        point_3d.append((-front_size, -front_size, front_depth))
        point_3d = np.array(point_3d, dtype=np.float32).reshape(-1, 3)

        # 映射到二维图像点
        (point_2d, _) = cv2.projectPoints(point_3d,
                                          rotation_vector,
                                          translation_vector,
                                          self.camera_matrix,
                                          self.dist_coeefs)
        point_2d = np.int32(point_2d.reshape(-1, 2))

        # 绘制所有线条
        cv2.polylines(image, [point_2d], True, color, line_width, cv2.LINE_AA)
        cv2.line(image, tuple(point_2d[1]), tuple(
            point_2d[6]), color, line_width, cv2.LINE_AA)
        cv2.line(image, tuple(point_2d[2]), tuple(
            point_2d[7]), color, line_width, cv2.LINE_AA)
        cv2.line(image, tuple(point_2d[3]), tuple(
            point_2d[8]), color, line_width, cv2.LINE_AA)

    def draw_axes(self, img, pose):
        R, t = pose
        img = cv2.drawFrameAxes(img, self.camera_matrix,
                                self.dist_coeefs, R, t, 30)

    def show_3d_model(self):
        from matplotlib import pyplot
        from mpl_toolkits.mplot3d import Axes3D
        fig = pyplot.figure()
        ax = Axes3D(fig)

        x = self.model_points_68[:, 0]
        y = self.model_points_68[:, 1]
        z = self.model_points_68[:, 2]

        ax.scatter(x, y, z)
        ax.axis('square')
        pyplot.xlabel('x')
        pyplot.ylabel('y')
        pyplot.show()
