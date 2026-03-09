import os
import sys
import time
import numpy as np
from scipy.interpolate import interp1d
import tifffile
import argparse
import imageio
from tqdm import tqdm
from natsort import natsorted
from multiprocessing import Pool
import glob

# Enable multithreading for NumPy operations (FFT, linear algebra)
# Set to 2-4 threads per process when running multiple processes in parallel
def thread_setup(cores: str = '1'):
    os.environ['OMP_NUM_THREADS'] = cores
    os.environ['MKL_NUM_THREADS'] = cores
    os.environ['OPENBLAS_NUM_THREADS'] = cores
    os.environ['NUMEXPR_NUM_THREADS'] = cores

def read_cfg(path):
    # Read .cfg file
    cfg_files = [f for f in os.listdir(path) if f.endswith('.cfg')]
    # Create a dictionary to hold configuration parameters
    cfg_dict = {}
    with open(os.path.join(path, cfg_files[0]), 'r') as file:
        cfg_lines = file.readlines()
    for line in cfg_lines:
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            # Attempt to type cast the value
            if value.isdigit():
                cfg_dict[key] = int(value)
            else:
                try:
                    cfg_dict[key] = float(value)
                except ValueError:
                        cfg_dict[key] = value.strip('"')
    return cfg_dict

def optimize(path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix, imRange):
    """Process first .dat file to determine crop parameters for X and Y axes."""
    dat_files = natsorted([f for f in os.listdir(path) if f.endswith('.dat')])
    
    # Process first file (or first one computer finds for speed)
    first_file = dat_files[0]
    print(f"Processing {first_file} to determine crop parameters...")
    print(f"Exit the visualization window to continue with cropping inputs.\n")
    
    with open(os.path.join(path, first_file), 'rb') as file:
        dat_data = file.read()
    
    # Interpolate to linear k-space
    raw_fringes = np.frombuffer(dat_data, dtype=np.uint8).reshape(
        cfg_dict['Acquisition Window Height'], cfg_dict['Acquisition Window Width'])
    interpolate_func = interp1d(k_space, raw_fringes, kind='linear', axis=1, fill_value="extrapolate")
    linear_k_space_fringes = interpolate_func(new_ks)
    
    # Compute FFT
    fft_result = np.fft.fft(linear_k_space_fringes.T * hann_rep_matrix.T, axis=0)
    magnitude = np.abs(fft_result)[1:len(spectrum)//2,:]
    image = 20*np.log10(magnitude)
    
    # Normalize
    image_clipped = np.clip(image, imRange[0], imRange[1])
    image_normalized = (image_clipped - imRange[0]) / (imRange[1] - imRange[0])
    image = (image_normalized * 255).astype(np.uint8)
    
    # Display image for user
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 8))
    plt.imshow(image, cmap='gray')
    plt.colorbar()
    plt.title('First frame for crop optimization')
    plt.xlabel('X axis')
    plt.ylabel('Y axis')
    plt.show()
    
    # Get X axis crop
    x_crop = input("Enter integer values separated by comma to crop X-axis (e.g., 50,400), or press Enter to skip: ")
    if x_crop:
        x_start, x_end = map(int, x_crop.split(','))
    else:
        x_start, x_end = 0, image.shape[1]
    
    # Get Y axis crop
    y_crop = input("Enter integer values separated by comma to crop Y-axis (e.g., 50,400), or press Enter to skip: ")
    if y_crop:
        y_start, y_end = map(int, y_crop.split(','))
    else:
        y_start, y_end = 0, image.shape[0]
    
    return (y_start, y_end, x_start, x_end)

def process_single_frame(args):
    """Process a single .dat file and save as TIFF. Designed for parallel execution."""
    dat_file, path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix, imRange, save_path, save_filename, counter, num_digits, crop_params = args
    
    # Read and process
    with open(os.path.join(path, dat_file), 'rb') as file:
        dat_data = file.read()
    
    # Interpolate to linear k-space
    raw_fringes = np.frombuffer(dat_data, dtype=np.uint8).reshape(
        cfg_dict['Acquisition Window Height'], cfg_dict['Acquisition Window Width'])
    interpolate_func = interp1d(k_space, raw_fringes, kind='linear', axis=1, fill_value="extrapolate")
    linear_k_space_fringes = interpolate_func(new_ks)
    
    # Compute FFT
    fft_result = np.fft.fft(linear_k_space_fringes.T * hann_rep_matrix.T, axis=0)
    magnitude = np.abs(fft_result)[1:len(spectrum)//2,:]
    image = 20*np.log10(magnitude)
    
    # Normalize
    image_clipped = np.clip(image, imRange[0], imRange[1])
    image_normalized = (image_clipped - imRange[0]) / (imRange[1] - imRange[0])
    image = (image_normalized * 255).astype(np.uint8)
    
    # Apply crop
    y_start, y_end, x_start, x_end = crop_params
    image = image[y_start:y_end, x_start:x_end]
    
    # Save as individual TIFF
    tifffile.imwrite(os.path.join(save_path, f'{save_filename}_image_{counter:0{num_digits}d}.tiff'), image)
    
    return counter

def process(path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix, imRange, save_path, crop_params, num_processes):
    """Process all .dat files in parallel and save as TIFF series."""
    dat_files = natsorted([f for f in os.listdir(path) if f.endswith('.dat')])
    loops = len(dat_files)
    save_filename = path.split('/')[-2]
    num_digits = len(str(loops))
    
    # Prepare arguments for parallel processing
    process_args = [
        (dat_files[i], path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix,
         imRange, save_path, save_filename, i, num_digits, crop_params)
        for i in range(loops)
    ]
    
    # Process all frames in parallel
    print(f"\nProcessing {loops} frames in parallel with {num_processes} processes...")
    with Pool(processes=num_processes) as pool:
        list(tqdm(pool.imap(process_single_frame, process_args),
                  total=loops, desc="Processing frames", unit="frame", dynamic_ncols=True))
    
    print(f"Saved TIFF series with {loops} frames\n")
    return save_filename, loops

def export(save_path, save_filename, save_modes, frame_rate, loops):
    """Create TIFF stack and/or MP4 video from TIFF series, then cleanup if needed."""
    tiff_files = natsorted(glob.glob(os.path.join(save_path, f'{save_filename}_image_*.tiff')))
    
    if 'tiff_stack' in save_modes:
        print("Creating TIFF stack from series...")
        tiff_stack_path = os.path.join(save_path, f'{save_filename}_image_stack.tiff')
        # Load all images and save as stack
        images = []
        for tiff_file in tqdm(tiff_files, desc="Loading images", unit="image"):
            images.append(tifffile.imread(tiff_file))
        tifffile.imwrite(tiff_stack_path, np.array(images))
        print(f"Saved TIFF stack with {loops} frames\n")
    
    if 'mp4' in save_modes:
        print("Creating MP4 video from series...")
        mp4_file = os.path.join(save_path, f'{save_filename}_video.mp4')
        mp4_writer = imageio.get_writer(mp4_file, fps=frame_rate, codec='libx264',
                                       pixelformat='yuv420p', quality=8)
        for tiff_file in tqdm(tiff_files, desc="Encoding video", unit="frame"):
            image = tifffile.imread(tiff_file)
            # Convert to RGB for QuickTime compatibility
            if len(image.shape) == 2:
                image_rgb = np.stack([image, image, image], axis=-1)
            else:
                image_rgb = image
            mp4_writer.append_data(image_rgb)
        mp4_writer.close()
        print(f"Saved MP4 video with {loops} frames\n")
    
    # Clean up TIFF series if not requested
    if 'tiff_series' not in save_modes:
        print("Removing temporary TIFF series files...")
        for tiff_file in tqdm(tiff_files, desc="Cleaning up", unit="file"):
            os.remove(tiff_file)
        print("Cleanup complete")

def process_and_save(path, cfg_dict, imRange, save_modes, save_path, frame_rate, num_processes):
    """Process .dat files in parallel and save as TIFF series to the tiffs directory.
    Then, depending on save_modes, will:
    - Leave the TIFF series in the directory (if 'tiff_series' in save_modes)
    - Convert the TIFF series into a TIFF stack (if 'tiff_stack' in save_modes)
    - Create an MP4 video from the series (if 'mp4' in save_modes)
    - Remove the TIFF series if 'tiff_series' is NOT in save_modes (cleanup)
    """
    # Get spectrum file
    spectrum_files = [f for f in os.listdir(path) if f.endswith('.spectrum')]
    spectrum = np.loadtxt(os.path.join(path, spectrum_files[0]))
    
    # Convert to k-space
    k_space = 2*np.pi/spectrum
    new_ks = k_space[0] - np.arange(len(k_space)) * (k_space[0] - k_space[-1]) / (len(k_space) - 1)
    
    # Create Hanning window matrix
    hann_rep_matrix = np.tile(np.hanning(len(k_space)), (cfg_dict['Acquisition Window Height'], 1))
    
    # Step 1: Optimize. Get crop parameters from first frame
    crop_params = optimize(path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix, imRange)
    
    # Step 2: Process. Parallelize processing and save each .dat file as TIFF
    save_filename, loops = process(path, cfg_dict, spectrum, k_space, new_ks, hann_rep_matrix, 
                                    imRange, save_path, crop_params, num_processes)
    
    # Step 3: Export. Create stack/video based on save_modes, and cleanup if needed
    export(save_path, save_filename, save_modes, frame_rate, loops)


def main(path, save_modes, imRange, frame_rate, num_threads, num_processes):
    # Step 1: Check if tiffs directory already exists
    save_path = os.path.join(path, 'tiffs')
    if os.path.exists(save_path):
        print(f"WARNING: {save_path} already exists!")
        print("\nTo continue, you must either:")
        print("  1. Rename the existing 'tiffs' directory, OR")
        print("  2. Delete the existing 'tiffs' directory")
        print("\nThis check ensures you don't accidentally overwrite existing data.")
        sys.exit(1)
    
    # Start timing
    start_time = time.time()
    
    # Step 2: Setup and read configuration
    thread_setup(str(num_threads))
    cfg_dict = read_cfg(path)
    os.makedirs(save_path)
    
    # Step 3: Process and save with three discrete steps
    process_and_save(path, cfg_dict, imRange, save_modes, save_path, frame_rate, num_processes)
    
    # Print total execution time
    elapsed_time = time.time() - start_time
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = elapsed_time % 60
    
    if hours > 0:
        print(f"Total execution time: {hours}h {minutes}m {seconds:.2f}s")
    elif minutes > 0:
        print(f"Total execution time: {minutes}m {seconds:.2f}s")
    else:
        print(f"Total execution time: {seconds:.2f}s")

if __name__ == "__main__":
    # Define arguments: path, and save mode using argparse
    parser = argparse.ArgumentParser(
        description='Process SDOCT .dat files in parallel and save as TIFF series to the tiffs directory. '
                    'Then, depending on save_modes, will: (1) Leave the TIFF series in the directory (if "tiff_series" in save_modes), '
                    '(2) Convert the TIFF series into a TIFF stack (if "tiff_stack" in save_modes), '
                    '(3) Create an MP4 video from the series (if "mp4" in save_modes), '
                    '(4) Remove the TIFF series if "tiff_series" is NOT in save_modes (cleanup).')
    parser.add_argument('path', type=str, help='Path to the directory containing .dat files and configuration.')
    parser.add_argument('--save_modes', nargs='+', default=['tiff_series'], 
                        choices=['tiff_series', 'tiff_stack', 'mp4'],
                        help='One or more save modes (e.g., --save_modes tiff_series mp4)')
    parser.add_argument('--imRange', type=str, default='0,80', help='Dynamic range for image display as comma-separated values (e.g., 0,80)')
    parser.add_argument('--frame_rate', type=int, default=100, help='Enter frame rate for mp4 saving (default: 100)')
    parser.add_argument('--num_threads', type=int, default=1, help='Number of threads for NumPy operations per process (default: 1)')
    parser.add_argument('--num_processes', type=int, default=4, help='Number of parallel processes for frame processing (default: 4)')
    args = parser.parse_args()
    main(args.path, args.save_modes, tuple(map(int, args.imRange.split(','))), args.frame_rate, args.num_threads, args.num_processes)