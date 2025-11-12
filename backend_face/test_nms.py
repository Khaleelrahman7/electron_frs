#!/usr/bin/env python3
"""
Test script to validate NMS (Non-Maximum Suppression) implementation in face_pipeline.py

This script tests the NMS functionality to ensure overlapping bounding boxes are properly eliminated.
"""

import numpy as np
from face_pipeline import calculate_iou, apply_nms, get_detector_info, set_nms_threshold


class MockFace:
    """Mock face detection object to simulate InsightFace output"""
    def __init__(self, bbox, det_score=1.0):
        self.bbox = np.array(bbox)
        self.det_score = det_score


def test_calculate_iou():
    """Test IoU calculation"""
    print("=" * 80)
    print("TEST 1: IoU Calculation")
    print("=" * 80)
    
    # Test case 1: Identical boxes (IoU = 1.0)
    bbox1 = (0, 0, 100, 100)
    bbox2 = (0, 0, 100, 100)
    iou = calculate_iou(bbox1, bbox2)
    print(f"Identical boxes: IoU = {iou:.2f} (expected: 1.00)")
    assert abs(iou - 1.0) < 0.01, "Identical boxes should have IoU = 1.0"
    
    # Test case 2: No overlap (IoU = 0.0)
    bbox1 = (0, 0, 100, 100)
    bbox2 = (200, 200, 300, 300)
    iou = calculate_iou(bbox1, bbox2)
    print(f"No overlap: IoU = {iou:.2f} (expected: 0.00)")
    assert iou == 0.0, "Non-overlapping boxes should have IoU = 0.0"
    
    # Test case 3: 50% overlap
    bbox1 = (0, 0, 100, 100)
    bbox2 = (50, 0, 150, 100)
    iou = calculate_iou(bbox1, bbox2)
    print(f"50% overlap: IoU = {iou:.2f} (expected: ~0.33)")
    
    # Test case 4: One box inside another
    bbox1 = (0, 0, 100, 100)
    bbox2 = (25, 25, 75, 75)
    iou = calculate_iou(bbox1, bbox2)
    print(f"One inside another: IoU = {iou:.2f} (expected: 0.25)")
    
    print("[PASS] IoU calculation tests passed!\n")


def test_nms_basic():
    """Test basic NMS functionality"""
    print("=" * 80)
    print("TEST 2: Basic NMS - Overlapping Boxes")
    print("=" * 80)
    
    # Create mock faces with overlapping boxes (simulating the issue)
    faces = [
        MockFace([100, 100, 200, 200], det_score=0.9),  # High confidence
        MockFace([110, 110, 210, 210], det_score=0.7),  # Overlapping, lower confidence
        MockFace([105, 105, 205, 205], det_score=0.6),  # Another overlap
        MockFace([500, 500, 600, 600], det_score=0.8),  # Different face, no overlap
    ]
    
    print(f"Before NMS: {len(faces)} detections")
    for i, f in enumerate(faces):
        print(f"  Face {i+1}: bbox={f.bbox}, score={f.det_score}")
    
    # Apply NMS with threshold 0.3
    filtered = apply_nms(faces, iou_threshold=0.3)
    
    print(f"\nAfter NMS (threshold=0.3): {len(filtered)} detections")
    for i, f in enumerate(filtered):
        print(f"  Face {i+1}: bbox={f.bbox}, score={f.det_score}")
    
    # Should keep only 2 faces (the highest confidence from overlapping group + the separate one)
    assert len(filtered) == 2, f"Expected 2 faces after NMS, got {len(filtered)}"
    assert filtered[0].det_score == 0.9, "Should keep highest confidence face"
    assert filtered[1].det_score == 0.8, "Should keep non-overlapping face"
    
    print("[PASS] Basic NMS test passed!\n")


def test_nms_no_overlap():
    """Test NMS with no overlapping boxes"""
    print("=" * 80)
    print("TEST 3: NMS - No Overlapping Boxes")
    print("=" * 80)
    
    # Create mock faces with no overlaps
    faces = [
        MockFace([100, 100, 200, 200], det_score=0.9),
        MockFace([300, 300, 400, 400], det_score=0.8),
        MockFace([500, 500, 600, 600], det_score=0.7),
    ]
    
    print(f"Before NMS: {len(faces)} detections")
    filtered = apply_nms(faces, iou_threshold=0.3)
    print(f"After NMS: {len(filtered)} detections")
    
    # Should keep all faces since no overlaps
    assert len(filtered) == 3, f"Expected 3 faces (no overlaps), got {len(filtered)}"
    
    print("[PASS] No overlap NMS test passed!\n")


def test_nms_threshold_sensitivity():
    """Test NMS behavior with different thresholds"""
    print("=" * 80)
    print("TEST 4: NMS Threshold Sensitivity")
    print("=" * 80)
    
    # Create overlapping boxes with varying degrees of overlap
    faces = [
        MockFace([100, 100, 200, 200], det_score=0.9),  # Base face
        MockFace([110, 110, 210, 210], det_score=0.8),  # High overlap (~64%)
        MockFace([150, 150, 250, 250], det_score=0.7),  # Medium overlap (~25%)
    ]
    
    # Test with different thresholds
    thresholds = [0.2, 0.3, 0.5, 0.7]
    for thresh in thresholds:
        filtered = apply_nms(faces, iou_threshold=thresh)
        print(f"Threshold {thresh}: {len(filtered)} faces kept (removed {len(faces) - len(filtered)})")
    
    print("[PASS] Threshold sensitivity test completed!\n")


def test_detector_info():
    """Test detector info retrieval"""
    print("=" * 80)
    print("TEST 5: Detector Configuration Info")
    print("=" * 80)
    
    info = get_detector_info()
    print("Current detector configuration:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    assert info['nms_enabled'] == True, "NMS should be enabled"
    assert 'nms_iou_threshold' in info, "Should have NMS threshold"
    
    print("[PASS] Detector info test passed!\n")


def test_set_nms_threshold():
    """Test dynamic NMS threshold adjustment"""
    print("=" * 80)
    print("TEST 6: Dynamic NMS Threshold Adjustment")
    print("=" * 80)
    
    # Test valid threshold
    set_nms_threshold(0.4)
    info = get_detector_info()
    print(f"New threshold: {info['nms_iou_threshold']}")
    assert info['nms_iou_threshold'] == 0.4, "Threshold should be updated to 0.4"
    
    # Test invalid threshold (should be rejected)
    print("\nTesting invalid threshold (1.5):")
    set_nms_threshold(1.5)
    info = get_detector_info()
    assert info['nms_iou_threshold'] == 0.4, "Invalid threshold should be rejected"
    
    # Reset to default
    set_nms_threshold(0.3)
    
    print("[PASS] Dynamic threshold adjustment test passed!\n")


def test_edge_cases():
    """Test edge cases"""
    print("=" * 80)
    print("TEST 7: Edge Cases")
    print("=" * 80)
    
    # Test with empty list
    faces = []
    filtered = apply_nms(faces, iou_threshold=0.3)
    print(f"Empty list: {len(filtered)} faces (expected: 0)")
    assert len(filtered) == 0, "Empty list should return empty list"
    
    # Test with single face
    faces = [MockFace([100, 100, 200, 200], det_score=0.9)]
    filtered = apply_nms(faces, iou_threshold=0.3)
    print(f"Single face: {len(filtered)} faces (expected: 1)")
    assert len(filtered) == 1, "Single face should return single face"
    
    # Test with all identical boxes (should keep only one)
    faces = [
        MockFace([100, 100, 200, 200], det_score=0.9),
        MockFace([100, 100, 200, 200], det_score=0.8),
        MockFace([100, 100, 200, 200], det_score=0.7),
    ]
    filtered = apply_nms(faces, iou_threshold=0.3)
    print(f"All identical: {len(filtered)} faces (expected: 1, highest score)")
    assert len(filtered) == 1, "Should keep only highest confidence box"
    assert filtered[0].det_score == 0.9, "Should keep highest score"
    
    print("[PASS] Edge cases test passed!\n")


def run_all_tests():
    """Run all NMS tests"""
    print("\n" + "=" * 80)
    print("FACE PIPELINE NMS VALIDATION TESTS")
    print("=" * 80 + "\n")
    
    try:
        test_calculate_iou()
        test_nms_basic()
        test_nms_no_overlap()
        test_nms_threshold_sensitivity()
        test_detector_info()
        test_set_nms_threshold()
        test_edge_cases()
        
        print("=" * 80)
        print("*** ALL TESTS PASSED! ***")
        print("=" * 80)
        print("\nNMS implementation is working correctly!")
        print("Overlapping bounding boxes will be properly eliminated.")
        print("\nKey findings:")
        print("  - IoU calculation is accurate")
        print("  - NMS successfully removes overlapping detections")
        print("  - Highest confidence boxes are preserved")
        print("  - Threshold adjustment works as expected")
        print("  - Edge cases handled properly")
        
    except AssertionError as e:
        print("\n" + "=" * 80)
        print("*** TEST FAILED! ***")
        print("=" * 80)
        print(f"Error: {e}")
        return False
    except Exception as e:
        print("\n" + "=" * 80)
        print("*** UNEXPECTED ERROR! ***")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

