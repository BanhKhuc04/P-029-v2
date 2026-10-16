"""Explicit, user-run weight installation. Preflight itself never downloads."""
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare-camera"])
    parser.add_argument("--model", choices=["maskrcnn", "gdino-sam2", "hybrid"], required=True)
    args = parser.parse_args()
    if args.model in ("maskrcnn", "hybrid"):
        from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights
        MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1.get_state_dict(progress=True, check_hash=True)
    if args.model in ("gdino-sam2", "hybrid"):
        from huggingface_hub import snapshot_download
        from pointsnap.vision.detector2d import GDINO_ID, GDINO_REVISION, SAM2_ID, SAM2_REVISION
        for repo, revision in ((GDINO_ID, GDINO_REVISION), (SAM2_ID, SAM2_REVISION)):
            snapshot_download(repo_id=repo, revision=revision, allow_patterns=["*.json", "*.safetensors", "*.txt"])
    print("Trọng số đã sẵn sàng. Bấm Kiểm tra lại trong PointSnap.")


if __name__ == "__main__":
    main()
