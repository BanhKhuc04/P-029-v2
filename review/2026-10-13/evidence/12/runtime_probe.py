"""CPU operator/processor smoke on a real image; explicitly NOT pretrained quality acceptance.

No weight downloads, no trained detections used as human verdicts. Random initialization is recorded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
TOOL=ROOT/'source-tool/pointsnap-3d'
sys.path.insert(0,str(TOOL))


def main():
    import numpy as np
    import torch,torchvision,transformers
    from PIL import Image
    from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights,maskrcnn_resnet50_fpn_v2
    from transformers import Sam2Processor
    from pointsnap.adapters.nuscenes.reader import NuScenesReader
    from pointsnap.vision.detector2d import Detector2D,SAM2_ID,SAM2_REVISION
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataroot',required=True)
    parser.add_argument('--cache-dir',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists() or args.cache_dir.exists():parser.error('Choose fresh paths')
    torch.set_num_threads(1);torch.manual_seed(12)
    reader=NuScenesReader(args.dataroot);ref=reader.samples('scene-0061')[0]
    view=next(v for v in reader.camera_views(ref) if v.channel=='CAM_FRONT')
    detector=Detector2D(cache_dir=args.cache_dir,device='cpu',min_score=0)
    # Real torchvision operators, small input for a contract smoke. All weights are random.
    detector._model=maskrcnn_resnet50_fpn_v2(weights=None,weights_backbone=None,min_size=64,max_size=64,
                                           box_score_thresh=0,box_detections_per_img=5).eval()
    detector._categories=list(MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1.meta['categories'])
    start=time.perf_counter();first=detector.detect(view.path);cold=time.perf_counter()-start
    start=time.perf_counter();second=detector.detect(view.path);warm=time.perf_counter()-start
    assert np.array_equal(first.boxes,second.boxes) and np.array_equal(first.scores,second.scores)
    assert first.names==second.names and all(np.array_equal(a,b) for a,b in zip(first.masks,second.masks))
    processor=Sam2Processor.from_pretrained(SAM2_ID,revision=SAM2_REVISION,use_fast=True,local_files_only=True)
    with Image.open(view.path) as image:
        inputs=processor(images=image.convert('RGB'),input_boxes=[[[0,0,100,100]]],return_tensors='pt')
    masks=processor.post_process_masks(torch.ones(1,1,1,256,256),inputs['original_sizes'])[0]
    assert tuple(masks.shape)==(1,1,900,1600)
    result={'device':'cpu','torch':torch.__version__,'torchvision':torchvision.__version__,
            'transformers':transformers.__version__,'scene':'scene-0061','frame':0,'channel':'CAM_FRONT',
            'image_sha256':hashlib.sha256(view.path.read_bytes()).hexdigest(),
            'maskrcnn_weights':'random initialization, seed 12; NO pretrained checkpoint',
            'maskrcnn_input_resize':'64 px maximum; contract smoke only','detections':len(first.names),
            'boxes_shape':list(first.boxes.shape),'mask_shapes':[list(m.shape) for m in first.masks],
            'cold_seconds':cold,'warm_seconds':warm,'cache_equal':True,
            'sam2_processor_revision':SAM2_REVISION,'sam2_processor_mask_shape':list(masks.shape),
            'sam2_predictions':'synthetic logits; no SAM2 model inference',
            'pretrained_quality_accepted':False,'human_verdicts_generated':0}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
