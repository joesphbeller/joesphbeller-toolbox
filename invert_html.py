#!/usr/bin/env python3
# Thanks to Github Copilot for helping me quickly implement the code. Specificially, handling all of the html jargon I honestly do not know.
# This script has not been tested yet.
"""
HTML Dark-Mode Inversion Script

This script reads one or more HTML files and injects a CSS block that applies
an inversion + hue rotation technique for an immediate dark-mode version.

By default, output files are written alongside the originals with
"_dark" appended to the filename.
"""

import argparse
import re
import sys
from pathlib import Path


DARK_MODE_STYLE_ID = "instant-dark-mode-invert"
DARK_MODE_STYLE = f"""<style id=\"{DARK_MODE_STYLE_ID}\">
html {{
  background: #111;
  filter: invert(1) hue-rotate(180deg);
}}

img,
video,
picture,
canvas,
svg,
iframe {{
  filter: invert(1) hue-rotate(180deg);
}}
</style>"""


def style_already_present(html_text: str) -> bool:
	return DARK_MODE_STYLE_ID in html_text


def inject_dark_mode_style(html_text: str) -> str:
	if style_already_present(html_text):
		return html_text

	head_open_pattern = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
	html_open_pattern = re.compile(r"<html\b[^>]*>", re.IGNORECASE)

	head_match = head_open_pattern.search(html_text)
	if head_match:
		insert_at = head_match.end()
		return (
			html_text[:insert_at]
			+ "\n"
			+ DARK_MODE_STYLE
			+ "\n"
			+ html_text[insert_at:]
		)

	html_match = html_open_pattern.search(html_text)
	if html_match:
		insert_at = html_match.end()
		return (
			html_text[:insert_at]
			+ "\n<head>\n"
			+ DARK_MODE_STYLE
			+ "\n</head>\n"
			+ html_text[insert_at:]
		)

	return "<head>\n" + DARK_MODE_STYLE + "\n</head>\n" + html_text


def get_output_path(input_path: Path, in_place: bool) -> Path:
	if in_place:
		return input_path
	return input_path.with_name(f"{input_path.stem}_dark{input_path.suffix}")


def process_file(input_path: Path, in_place: bool, overwrite: bool) -> bool:
	if not input_path.exists() or not input_path.is_file():
		print(f"Error: '{input_path}' is not a valid file.")
		return False

	try:
		html_text = input_path.read_text(encoding="utf-8")
	except UnicodeDecodeError:
		print(f"Error: '{input_path}' is not valid UTF-8 text.")
		return False
	except Exception as exc:
		print(f"Error reading '{input_path}': {exc}")
		return False

	updated_text = inject_dark_mode_style(html_text)
	output_path = get_output_path(input_path, in_place)

	if output_path.exists() and output_path != input_path and not overwrite:
		print(
			f"Skipped '{input_path}': output '{output_path.name}' already exists. "
			"Use --overwrite to replace it."
		)
		return False

	try:
		output_path.write_text(updated_text, encoding="utf-8")
	except Exception as exc:
		print(f"Error writing '{output_path}': {exc}")
		return False

	if style_already_present(html_text):
		print(f"No change needed (style already present): {input_path}")
	else:
		print(f"Wrote dark-mode HTML: {output_path}")
	return True


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Inject immediate dark-mode inversion CSS into one or more HTML files."
		)
	)
	parser.add_argument("files", nargs="+", help="HTML files to process")
	parser.add_argument(
		"--in-place",
		action="store_true",
		help="Modify files in place instead of creating *_dark.html outputs",
	)
	parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Overwrite existing output files when not using --in-place",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	successes = 0

	for file_arg in args.files:
		path = Path(file_arg)
		if process_file(path, in_place=args.in_place, overwrite=args.overwrite):
			successes += 1

	if successes == 0:
		sys.exit(1)


if __name__ == "__main__":
	main()
