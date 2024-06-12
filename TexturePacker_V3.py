import numpy as np
from PIL import Image
from tkinter import Tk, Label, Button, filedialog
from tkinter.ttk import Progressbar
import cv2
import os


def get_transparent_percentage(image):
    alpha_channel = image[:, :, 3]
    # prevent division by zero
    if alpha_channel.size == 0:
        return 10
    return np.count_nonzero(alpha_channel == 0) / alpha_channel.size

# increment scales by 0.01
scales = np.arange(0.5, 1.0, 0.1)


def process_image(image_paths, scale, scale2):
    all_rects = []
    all_images = []
    waste_areas = []
    waste_percentage = 0
    for image_path in image_paths:
        # Load the image
        image = Image.open(image_path)
        image_np = np.array(image)

        # Add an alpha channel if it doesn't exist
        if image_np.shape[2] == 3:
            alpha_channel = (
                np.ones((image_np.shape[0], image_np.shape[1], 1), dtype=np.uint8) * 255
            )
            image_np = np.concatenate((image_np, alpha_channel), axis=2)

        all_images.append(image_np)

        # Check if the image is fully opaque
        if np.all(image_np[:, :, 3] == 255):
            # Treat the entire image as a single rectangle
            rects = [(0, 0, image_np.shape[1], image_np.shape[0])]
        else:
            gray = cv2.cvtColor(image_np, cv2.COLOR_RGBA2GRAY)
            _, thresh = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)

            # Find contours
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # Get bounding rectangles for each contour
            rects = [cv2.boundingRect(cnt) for cnt in contours]

            # Ensure at least one rectangle
            if not rects:
                rects = [(0, 0, image_np.shape[1], image_np.shape[0])]
                # Store rectangles with their corresponding image index
        all_rects.extend([(rect, len(all_images) - 1) for rect in rects])
    for img in all_images:
        waste_areas.append(get_transparent_percentage(img))
    waste_percentage = sum(waste_areas) / len(waste_areas)
    # Sort rectangles by height (largest to smallest)
    # split all_rects into two halves, sort each half, then merge
    all_rects = sorted(all_rects, key=lambda x: x[0][3], reverse=True)
    # half1 = []
    # half2 = []
    # # alternate between adding to half1 and half2
    # for i, rect in enumerate(all_rects):
    #     if i % 2 == 0:
    #         half1.append(rect)
    #     else:
    #         half2.append(rect)
    # all_rects = half1 + half2
    # Initialize free rectangles with one big rectangle
    max_width = max(image.shape[1] * scale for image in all_images)
    max_height = sum(image.shape[0] * scale2 for image in all_images)
    free_rects = [(0, 0, max_width, max_height)]

    packed_positions = []

    for rect, img_idx in all_rects:
        w, h = rect[2], rect[3]
        best_free_rect = None
        best_free_rect_idx = -1
        best_fit = None

        # Find the best fitting free rectangle
        for i, free_rect in enumerate(free_rects):
            fw, fh = free_rect[2], free_rect[3]
            if fw >= w and fh >= h:
                fit = fh - h
                if best_fit is None or fit < best_fit:
                    best_fit = fit
                    best_free_rect = free_rect
                    best_free_rect_idx = i

        if best_free_rect is None:
            continue

        # Place the rectangle in the best fitting free rectangle
        fx, fy, fw, fh = best_free_rect
        packed_positions.append(
            (fx, fy, w, h, rect[0], rect[1], img_idx)
        )  # packedx, packedy, packedw, packedh, offsetx, offsety, img index
        # Split the free rectangle
        new_free_rects = []
        new_free_rects.append((fx + w, fy, fw - w, h))  # Right part
        new_free_rects.append((fx, fy + h, fw, fh - h))  # Bottom part

        # Replace the used free rectangle
        free_rects.pop(best_free_rect_idx)
        for new_free_rect in new_free_rects:
            if new_free_rect[2] > 0 and new_free_rect[3] > 0:
                free_rects.append(new_free_rect)

    # Create a new packed image with the calculated size
    if packed_positions:
        max_width = max(px + pw for px, _, pw, _, _, _, _ in packed_positions)
        max_height = max(py + ph for _, py, _, ph, _, _, _ in packed_positions)
    else:
        max_width = 0  # Or another default value
        max_height = 0
    packed_image = np.zeros((max_height, max_width, 4), dtype=np.uint8)

    # Place rectangles into the packed image
    for (
        px,
        py,
        pw,
        ph,
        ox,
        oy,
        img_idx,
    ) in (
        packed_positions
    ):  # px, py: position, pw, ph: width, height, ox, oy: offset x, y in the original image
        packed_image[py : py + ph, px : px + pw] = all_images[img_idx][
            oy : oy + ph, ox : ox + pw
        ]

    return packed_image, waste_percentage, len(packed_positions), len(all_rects)


def pack_rectangles(image_paths, output_path, status_label, progress_bar):
    total_images = len(image_paths)
    progress_bar["maximum"] = total_images
    progress = 0

    for image_path in image_paths:
        # Update status and progress bar
        progress += 1
        status_label.config(text=f"Processing {image_path} ({progress}/{total_images})")
        progress_bar["value"] = progress
        root.update_idletasks()
    lowest_waste = 1
    best_scale_idx = -1
    best_scale_idy = -1
    for scale, i in enumerate(scales):
        for scale2, j in enumerate(scales):
            packed_image, _, positions, rects = process_image(image_paths, i, j)
            if positions != rects:
                print(f"Scale: {scale},{scale2}, invalid packing")
                continue
            waste_percentage = get_transparent_percentage(packed_image)
            print(f"Scale: {scale},{scale2}, waste: {waste_percentage * 100:.2f}%")
            if waste_percentage < lowest_waste:
                lowest_waste = waste_percentage
                best_scale_idx = i
                best_scale_idy = j
                print(
                    f"Best scale: {scale}, waste: {waste_percentage * 100:.2f}% {best_scale_idx}"
                )
    packed_image, waste_percentage, _, _ = process_image(
        image_paths, best_scale_idx, best_scale_idy
    )

    packed_image_pil = Image.fromarray(packed_image)

    # Save the packed image
    packed_image_pil.save(output_path)
    print(f"Packed image saved to {output_path}")

    # Update status
    status_label.config(
        text=f"Packed image saved to {output_path}\nStarted with waste of {waste_percentage * 100:.2f}%\nFinal waste of {get_transparent_percentage(packed_image) * 100:.2f}%"
    )
    progress_bar["value"] = 0


def open_file_dialog():
    file_paths = filedialog.askopenfilenames(
        filetypes=[
            ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.gif"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg;*.jpeg"),
            ("BMP files", "*.bmp"),
            ("TIFF files", "*.tiff"),
            ("GIF files", "*.gif"),
            ("All files", "*.*"),
        ]
    )
    if file_paths:
        output_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg;*.jpeg"),
                ("BMP files", "*.bmp"),
                ("TIFF files", "*.tiff"),
                ("GIF files", "*.gif"),
                ("All files", "*.*"),
            ],
        )
        if output_path:
            pack_rectangles(file_paths, output_path, status_label, progress_bar)


if __name__ == "__main__":
    root = Tk()
    root.title("Image Packer")
    root.geometry("400x200")

    label = Label(
        root, text="Select image files to pack", wraplength=350, justify="center"
    )
    label.pack(pady=10)

    button = Button(root, text="Browse", command=open_file_dialog)
    button.pack(pady=10)

    status_label = Label(root, text="", wraplength=350, justify="center")
    status_label.pack(pady=10)

    progress_bar = Progressbar(
        root, orient="horizontal", length=300, mode="determinate"
    )
    progress_bar.pack(pady=10)

    root.mainloop()
