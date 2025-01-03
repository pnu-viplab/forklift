#######################################
# Multi-camera image → Panorama image #
#######################################

import torch, glob, cv2, os
import numpy as np
import re

# Multi camera stitching 함수 정의
def stitch_images(img1, img2, mkpts0, mkpts1, inliers):
    inlier_pts0 = mkpts0[inliers.flatten()]
    inlier_pts1 = mkpts1[inliers.flatten()]
    H, _ = cv2.findHomography(inlier_pts1, inlier_pts0, cv2.USAC_MAGSAC)

    height1, width1, _ = img1.shape
    height2, width2, _ = img2.shape
    
    warped_img2 = cv2.warpPerspective(img2, H, (width1 + width2, max(height1, height2)))
    stitched_image = np.zeros((height1, width1 + width2, 4), dtype=np.uint8)
    stitched_image[:height1, :width1] = img1

    for y in range(height1):
        for x in range(width1 + width2):
            alpha1 = stitched_image[y, x, 3] / 255.0 
            alpha2 = warped_img2[y, x, 3] / 255.0  
            for c in range(3):
                stitched_image[y, x, c] = (
                    alpha1 * stitched_image[y, x, c] +
                    alpha2 * warped_img2[y, x, c] * (1 - alpha1)
                )
            stitched_image[y, x, 3] = min(255, (alpha1 + alpha2) * 255)

    non_zero_coords = np.argwhere(stitched_image[:, :, 3] > 0)
    top_left = non_zero_coords.min(axis=0)
    bottom_right = non_zero_coords.max(axis=0)

    return stitched_image[top_left[0]:bottom_right[0] + 1, top_left[1]:bottom_right[1] + 1]
    

# 자연 정렬 키
#  ▶ 이미지가 뒤죽박죽 섞이지 않도록 문자열을 자연 정렬
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

# 저장된 matching point를 로드
first_results = torch.load("matching_point/first_matching.pt")
second_results = torch.load("matching_point/second_matching.pt")
third_results = torch.load("matching_point/third_matching.pt")

# multi image 파일 경로와 파노라마로 저장할 경로 설정
image_files = [
    sorted(glob.glob(f"input_data/{str(i).zfill(2)}/*.png"), key=natural_sort_key)
    for i in range(1, 9)
]
output_folder = "panorama"
os.makedirs(output_folder, exist_ok=True)

# multi image 로드
images = [[cv2.imread(file, cv2.IMREAD_UNCHANGED) for file in files] for files in image_files]
min_count = min(len(files) for files in image_files)
print(len(images), len(images[0]), min_count)


# 스티칭 반복. 
for idx in range(min_count):
    current_images = [ch[idx] for ch in images]

    i = 0
    first_images = []
    for result in first_results: # 1번 스티칭 : 8장 → 4장 (0↔1, 2↔3, 4↔5, 6↔7)
        if i == 8 : break
        pair = result["pair"]
        mkpts0 = result["keypoints0"]
        mkpts1 = result["keypoints1"]
        inliers = result["inliers"]
        
        stitched = stitch_images(current_images[i], current_images[i + 1], mkpts0, mkpts1, inliers)
        first_images.append(stitched)
        i += 2

    second_images = []
    j=0
    for result in second_results : # 2번 스티칭 : 4장 → 2장 (01↔23, 45↔67)
        if j == 4 : break
        pair = result["pair"]
        mkpts0 = result["keypoints0"]
        mkpts1 = result["keypoints1"]
        inliers = result["inliers"]

        stitched = stitch_images(first_images[j], first_images[j + 1], mkpts0, mkpts1, inliers)
        second_images.append(stitched)
        j += 2

    k = 0
    for result in third_results : # 3번 스티칭 : 2장 → 1장 (0123↔4567)
        pair = result["pair"]
        mkpts0 = result["keypoints0"]
        mkpts1 = result["keypoints1"]
        inliers = result["inliers"]

        stitched_image = stitch_images(second_images[k], second_images[k+1], mkpts0, mkpts1, inliers)
        k += 2

    # 파노라마 이미지 저장
    output_path = os.path.join(output_folder, f"stitched_{idx}.jpg")
    cv2.imwrite(output_path, stitched_image)
