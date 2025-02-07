from typing import List

import tensorflow_datasets as tfds
from pose_format import Pose, PoseHeader
from pose_format.numpy import NumPyPoseBody
from pose_format.pose_header import PoseNormalizationInfo
from pose_format.pose_visualizer import PoseVisualizer
from pose_format.utils.reader import BufferReader
from sign_language_datasets.datasets.config import SignDatasetConfig
from tqdm import tqdm

from dataset.data_types import DataItemObject, TextPoseDatum, TextPoseDataset, TextPoseItem
from utils.pose_utils import pose_normalization_info, pose_hide_legs

DEFAULT_COMPONENTS = ["POSE_LANDMARKS", "LEFT_HAND_LANDMARKS", "RIGHT_HAND_LANDMARKS"]
MAX_SEQ_SIZE = 1000


def process_datum(datum: DataItemObject,
                  pose_header: PoseHeader,
                  normalization_info: PoseNormalizationInfo,
                  components: List[str] = None) -> List[TextPoseDatum]:
    # Get current object poses as dictionary
    tf_poses = {"": datum.pose} if datum.pose is not None else datum.poses

    # Create dictionary of all poses as Pose element
    text_poses_datum = []
    for key, tf_pose in tf_poses.items():
        fps = int(tf_pose.fps.numpy())
        pose_body = NumPyPoseBody(fps, tf_pose.data.numpy(), tf_pose.conf.numpy())
        pose = Pose(pose_header, pose_body)

        # Get subset of components if needed
        if components and len(components) != len(pose_header.components):
            pose = pose.get_components(components)

        # Normalize pose element
        # pose = pose.normalize(normalization_info)

        # Zero confidence of legs component
        pose_hide_legs(pose)

        # Remove unnecessary components
        pose.body.data = pose.body.data[:, :, :, :3]  # X,Y,Z
        # Prune all leading frames containing only zeros
        for i in range(len(pose.body.data)):
            if pose.body.confidence[i].sum() != 0:
                if i != 0:
                    pose.body.data = pose.body.data[i:]
                    pose.body.confidence = pose.body.confidence[i:]
                break

        # Insert all text pose datum object to list
        text = datum.hamnosys.numpy().decode('utf-8').strip()
        text_poses_datum.append(TextPoseDatum(id=datum.id,
                                              text=text,
                                              pose=pose,
                                              length=max(len(pose.body.data), len(text) + 1)))

    return text_poses_datum


def load_dataset(split="train") -> TextPoseDataset:
    config = SignDatasetConfig(name="cearing", version="1.0.0", include_video=False, fps=25, include_pose="holistic")

    # Loading Dicta sign data set
    dicta_sign = tfds.load(name='dicta_sign', builder_kwargs={"config": config},split=split)

    # Read the header data according to pose body structure
    with open("holistic.header", "rb") as buffer:
        pose_header = PoseHeader.read(BufferReader(buffer.read()))

    normalization_info = pose_normalization_info(pose_header)

    # Get all data in english from train dataset
    dicta_sign_train = filter(lambda data_item: data_item['spoken_language'].numpy().decode('utf-8') == "en",
                              dicta_sign["train"])

    # Convert list of list of TextPoseDatum to one list
    text_pose_data = [d for data_item in tqdm(dicta_sign_train) for d in process_datum(DataItemObject(**data_item),
                                                                                       pose_header,
                                                                                       normalization_info,
                                                                                       DEFAULT_COMPONENTS) if
                      d.length < MAX_SEQ_SIZE]

    return TextPoseDataset(text_pose_data)


# Show video os specific pose via Pose API
def pose_visualizer(pose: Pose, video_path: str):
    p = PoseVisualizer(pose)
    p.save_video(video_path, p.draw())


# Example for the above code
if __name__ == '__main__':
    datum: TextPoseItem = load_dataset()[0]
    pose_visualizer(datum.pose.obj, "results/example-video2.mp4")
    print(load_dataset()[0].text)
