# HELPFUL TERMINAL COMMANDS
These have been in my Mac's notes basically since my undergraduate, so I figured I could store them in a better place.

**NOTE:** `'$word'` --> ALWAYS indicating input, where `word` is a short describer of what you should put here instead of `'$word'`

---

## wsl user login

```bash
wsl -u $username
```

## Convert .avi to .mp4 with conserving frame rate and resolution

```bash
ffmpeg -i "$input_file" -c:v libx264 -c:a aac -strict experimental -r ntsc -vf "scale=iw:ih" "$output_file"
```

## Reading out contents of file while file updates

```bash
tail -f file.out
```

## Mounting a network in terminal

```bash
sudo mount -t drvfs '$network location' $dir_to_mount
```

## Remote mounting on Windows

In powershell:

```powershell
net use Z: $server_name
```
Z: can be any partion label (ie. Y: or X:. or Q: for all I care)

In wsl after:

```bash
sudo mount -t drvfs $server_name $dir_name
```

Then, when opening a folder, just enter `Z:` into search bar

## Running docker with mounting to a local repo:

```bash
docker run -it -v $dir_to_mount --name myRivet -p 8888:8888 $docker_image
```

## Combining pdfs

```bash
convert -density 300 $file1.pdf $file2.pdf -quality 100 $combined.pdf
```

## List available accounts on cluster that you have access to (in SLURM)

```bash
sacctmgr list association -p
```

## Moving N most recent files added to pwd to a subdirectory

```bash
mv $(ls -t | head -n 4) ./$subdirectory_location/
```

## Showing an image in RStudio

```r
library(plotly)
library(EBImage)
plot_ly(type="image", z = sarcoma@images$slice1.008um@image*255)
```