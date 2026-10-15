"""Verify >= 90% detection rate on basic geometric errors on the 5 held-out scenes."""
import json
from pathlib import Path
from pointsnap.adapters.nuscenes import NuScenesReader
from pointsnap.core.config import load_config
from pointsnap.core.model import add_track_markers, Severity
from pointsnap.core.scanner import scan_cuboids
from pointsnap.core.synthetic import inject_dataset
from pointsnap.eval.evaluate import matches, LARGE, magnitude_key
from pointsnap.eval.split import TEST_SCENES

def main():
    reader = NuScenesReader(Path('D:/Vin_uni/data/nuscenes'))
    cfg = load_config(env={})

    results = {}
    total_injected = 0
    total_detected = 0
    total_large = 0
    total_large_as_error = 0

    # Basic geometric error types
    basic_types = {"floating", "size_in_track", "track_jump", "heading_rotate"}

    for scene in TEST_SCENES:
        frames = reader.frames(scene)
        base_cuboids = add_track_markers(reader.annotations(scene), frames.num_frames)
        
        # Test 1 round of synthetic injection with seed 42, catalog core
        injected_cuboids, errors = inject_dataset(base_cuboids, seed=42, error_rate=0.15, offset=0, catalog="all")
        findings = scan_cuboids(injected_cuboids, cfg, frames)

        for err in errors:
            if err.error_type not in basic_types:
                continue
            mag = magnitude_key(err)
            key = f"{err.error_type}|{mag}"
            if key not in results:
                results[key] = {"injected": 0, "detected": 0, "as_error": 0}
            
            results[key]["injected"] += 1
            total_injected += 1

            # Match finding
            matched_findings = [f for f in findings if matches(err, f)]
            is_detected = len(matched_findings) > 0
            if is_detected:
                results[key]["detected"] += 1
                total_detected += 1

            is_large = (err.error_type, mag) in LARGE
            if is_large:
                total_large += 1
                if any(f.severity == Severity.ERROR for f in matched_findings):
                    total_large_as_error += 1
                    results[key]["as_error"] += 1

    summary = {
        "total_basic_injected": total_injected,
        "total_basic_detected": total_detected,
        "overall_basic_recall": total_detected / total_injected if total_injected else 0,
        "large_injected": total_large,
        "large_as_error": total_large_as_error,
        "large_severity_accuracy": total_large_as_error / total_large if total_large else 0,
        "by_error_and_magnitude": results
    }

    out_path = Path("review/2026-10-14/evidence/g7/geometric-recall-verification.json")
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
