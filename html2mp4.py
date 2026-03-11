#!/usr/bin/env python3
"""
Convert Matplotlib HTML animation files into MP4 movies.

This script targets HTML files produced by Matplotlib's JSHTML animation output,
where frames are embedded as lines like:
	frames[0] = "data:image/png;base64,...";
"""

import argparse
import base64
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FRAME_PATTERN = re.compile(
	r"frames\[(\d+)\]\s*=\s*[\"']data:image/([a-zA-Z0-9.+-]+);base64,([^\"']+)[\"']\s*;"
)
INTERVAL_PATTERN = re.compile(
	r"new\s+Animation\s*\([^\)]*?,\s*[^,]+,\s*[^,]+,\s*(\d+)\s*,",
	re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Extract frames from Matplotlib animation HTML and create MP4."
	)
	parser.add_argument("html_file", help="Path to Matplotlib animation HTML file")
	parser.add_argument(
		"-o",
		"--output",
		help="Output MP4 path (default: <html_stem>.mp4)",
	)
	parser.add_argument(
		"--fps",
		type=float,
		default=None,
		help="Override frames-per-second (default: inferred from HTML interval)",
	)
	parser.add_argument(
		"--keep-frames",
		action="store_true",
		help="Keep extracted frame files in <html_stem>_frames",
	)
	parser.add_argument(
		"--extract-only",
		action="store_true",
		help="Only extract frames, do not call ffmpeg",
	)
	return parser.parse_args()


def detect_fps(html_text: str) -> float:
	match = INTERVAL_PATTERN.search(html_text)
	if not match:
		return 20.0
	interval_ms = float(match.group(1))
	if interval_ms <= 0:
		return 20.0
	return 1000.0 / interval_ms


def extract_frames(html_text: str):
	normalized = html_text.replace("\\\n", "")
	frames = {}

	for match in FRAME_PATTERN.finditer(normalized):
		index = int(match.group(1))
		image_ext = match.group(2).lower().replace("jpeg", "jpg")
		payload = re.sub(r"\s+", "", match.group(3))
		try:
			data = base64.b64decode(payload, validate=True)
		except Exception as exc:
			raise ValueError(f"Failed to decode base64 for frame {index}: {exc}") from exc
		frames[index] = (image_ext, data)

	if not frames:
		raise ValueError(
			"No embedded frames found. Ensure this is a Matplotlib JSHTML animation file."
		)

	ordered = [frames[i] for i in sorted(frames.keys())]
	return ordered


def write_frames(frames, target_dir: Path) -> str:
	target_dir.mkdir(parents=True, exist_ok=True)
	first_ext = frames[0][0]

	for frame_idx, (ext, data) in enumerate(frames):
		if ext != first_ext:
			raise ValueError(
				"Mixed image formats in embedded frames are not supported by this quick script."
			)
		frame_file = target_dir / f"frame_{frame_idx:06d}.{first_ext}"
		frame_file.write_bytes(data)

	return first_ext


def run_ffmpeg(frames_dir: Path, extension: str, fps: float, output_path: Path) -> None:
	ffmpeg_path = shutil.which("ffmpeg")
	if ffmpeg_path is None:
		raise RuntimeError(
			"ffmpeg is not installed or not on PATH. Install ffmpeg, or run with --extract-only."
		)

	input_pattern = str(frames_dir / f"frame_%06d.{extension}")
	cmd = [
		ffmpeg_path,
		"-y",
		"-framerate",
		f"{fps:.6f}",
		"-i",
		input_pattern,
		"-c:v",
		"libx264",
		"-pix_fmt",
		"yuv420p",
		str(output_path),
	]
	result = subprocess.run(cmd, capture_output=True, text=True)
	if result.returncode != 0:
		raise RuntimeError(
			"ffmpeg failed:\n"
			+ (result.stderr.strip() or result.stdout.strip() or "unknown error")
		)


def main() -> None:
	args = parse_args()
	html_path = Path(args.html_file)

	if not html_path.exists() or not html_path.is_file():
		print(f"Error: '{html_path}' is not a valid file.")
		sys.exit(1)

	output_path = Path(args.output) if args.output else html_path.with_suffix(".mp4")

	try:
		html_text = html_path.read_text(encoding="utf-8")
	except Exception as exc:
		print(f"Error reading '{html_path}': {exc}")
		sys.exit(1)

	fps = args.fps if args.fps and args.fps > 0 else detect_fps(html_text)

	try:
		frames = extract_frames(html_text)
	except Exception as exc:
		print(f"Error extracting frames: {exc}")
		sys.exit(1)

	print(f"Found {len(frames)} frames at ~{fps:.3f} FPS")

	if args.keep_frames:
		frames_dir = html_path.with_name(f"{html_path.stem}_frames")
		try:
			ext = write_frames(frames, frames_dir)
		except Exception as exc:
			print(f"Error writing frames: {exc}")
			sys.exit(1)
		print(f"Frames written to: {frames_dir}")
	else:
		with tempfile.TemporaryDirectory(prefix="html2mp4_frames_") as temp_dir_name:
			frames_dir = Path(temp_dir_name)
			try:
				ext = write_frames(frames, frames_dir)
			except Exception as exc:
				print(f"Error writing temporary frames: {exc}")
				sys.exit(1)

			if args.extract_only:
				extract_dir = html_path.with_name(f"{html_path.stem}_frames")
				extract_dir.mkdir(parents=True, exist_ok=True)
				for frame_file in frames_dir.iterdir():
					shutil.copy2(frame_file, extract_dir / frame_file.name)
				print(f"Frames extracted to: {extract_dir}")
				return

			try:
				run_ffmpeg(frames_dir, ext, fps, output_path)
			except Exception as exc:
				print(exc)
				sys.exit(1)

			print(f"MP4 written to: {output_path}")
			return

	if args.extract_only:
		return

	try:
		run_ffmpeg(frames_dir, ext, fps, output_path)
	except Exception as exc:
		print(exc)
		sys.exit(1)

	print(f"MP4 written to: {output_path}")


if __name__ == "__main__":
	main()
