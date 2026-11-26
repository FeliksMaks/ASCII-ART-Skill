---
name: ascii-motion-graphics
description: Make ASCII art and ASCII motion graphics. (1) Have an LLM (any model, local or hosted, over an OpenAI-compatible chat API) write an ASCII animation program, check it safely, refine it from feedback and render it to MP4 or PNG, with run stats (tokens, time, tok/s). (2) Turn a photo or image into ASCII art - text, PNG or a short video (reveal, zoom, pan, scan, glitch), mono or in the photo's colours. Use when asked for ASCII art, an ASCII animation, a terminal-style motion graphic, a photo as ASCII, or a "the model wrote this" demo video.
---

# ASCII art and motion graphics

Two modes:

- **A model writes the animation.** The model writes one pure function, `frame(t)`, that returns the text of one frame.
  You check the code, run it, and draw the frames to a video. The model never runs anything itself, so this works safely
  with any model, and the frames come out the same on every run.
- **A photo becomes ASCII art.** `scripts/photo.py` converts an image, with no model involved.

## What you need

- For the model mode, a chat endpoint: `POST <base>/v1/chat/completions` (llama.cpp server, vLLM, LM Studio, Ollama's
  `/v1`, OpenRouter...).
- Python 3.9+ with Pillow. The MP4 also needs ffmpeg on PATH.
- A monospace font. `render.py` tries Cascadia Mono, Consolas, DejaVu Sans Mono and Menlo, or you can pass `--font`.

## The contract the scripts rely on

Write your own prompt for the subject you want, and state these rules in it:

- Python 3 that uses only the `math` module, with no other imports, files, printing or input.
- Exactly one function, `def frame(t):`, with `t` in seconds from 0 up to the loop length.
- It returns a list of `--rows` strings, each exactly `--cols` characters long. The defaults are 45 and 140, and must
  match what you pass to `frames.py`.
- Shading from dark to bright with a character ramp, such as `" .,-~:;=!*#$@"`, which `render.py` colours by default.
- A motion that loops smoothly over the clip's length.
- The reply is one ```python block holding the whole program.

Asking for real 3D math (rotation, perspective projection, a depth buffer, a light) gives far better results than asking
for "an animation".

## Steps

1. **Ask for several samples.** Send the same prompt with a few different `--seeds`. Small models vary a lot from one
   sample to the next, so this gives you a choice.

   ```
   python -I scripts/ask.py --base http://127.0.0.1:8080 --model <name> --prompt prompt.txt --seeds 1 2 3 --out work
   ```

   For a hosted API, add `--key-env OPENAI_API_KEY`, which takes the name of the variable, never the key itself. For a
   thinking model, add `--reasoning low|medium|high`. `ask.py` prints the tokens, seconds and tok/s of each answer, and
   logs them to `work/runs.jsonl`.

2. **Check before running.** `python -I scripts/check.py work/art1.py` rejects any import other than `math`, and any
   `open`, `exec`, `eval`, `__import__`, dunder, or file or network use. Read the code anyway, because the check is a
   filter, not a sandbox. Do not run code that fails it.

3. **Make the frames.** `python -I scripts/frames.py work/art1.py work/f1.json --fps 30 --seconds 12` runs `frame(t)` in
   a child process with a time limit, and checks each frame's shape.

4. **Look at stills before the video.** `python -I scripts/render.py work/f1.json work/a1.mp4 --still 0,90,180` writes
   PNGs. Common faults are a shape that overflows the frame, holes from sampling a surface too sparsely, a stretched shape
   from ignoring that characters are about twice as tall as wide, and a jump at the loop point.

5. **Feedback round.** Write what you saw as specific, measurable fixes, and send them with the code:
   `ask.py ... --prompt feedback.txt --code work/art1.py --tag v2_`. Name sizes, densities and counts rather than "make
   it better". One round is usually enough, so stop when a still looks right.

6. **Render the video.** `python -I scripts/render.py work/fv2_1.json out.mp4 --loops 2 --caption "..." --brand "..."`
   gives 1920x1080 at 30 fps in H.264, which most sites accept. Keep the caption true.

7. **Stats.** `python -I scripts/stats.py work/runs.jsonl <names of the answers you used>` adds up their tokens, time
   and tok/s, and those of all samples. The tok/s measured by the client includes reading the prompt. For decode speed
   alone, use the server's own log.

## Photo to ASCII art

```
python -I scripts/photo.py photo.jpg work/me --cols 140 --color          # work/me.txt + work/me.json
python -I scripts/render.py work/me.json work/me.png --still 0          # a 1080p PNG (written as work/me_0.png)
python -I scripts/photo.py photo.jpg work/me --color --motion reveal --seconds 8
python -I scripts/render.py work/me.json work/me.mp4 --loops 1
```

- `--cols`: the width in characters. 100-160 suits a 1080p video; 60-80 suits a chat or a README. The rows follow the
  image's shape, because a character is about twice as tall as wide (`--aspect`).
- `--ramp`: `classic` (13 levels), `fine` (70 levels, more detail), `blocks` (░▒▓█), `simple`, or your own string from
  dark to bright.
- `--color` draws each character in the photo's hue, with its brightness lifted so it reads on a dark background.
  `--true-color` keeps the exact colours.
- `--edges 0.2-0.4` mixes in outlines, which helps faces, logos and small subjects. Use `--gamma` (below 1 brightens the
  shadows) and `--contrast` for dark or flat photos, and `--invert` for a light background.
- `--motion`: `reveal`, `zoom`, `pan`, `scan`, `glitch`, or `none` for one frame.
- Crop the photo to the subject first. A face that fills the frame reads far better than a small one.
- For a model-written animation built on a photo, put `work/me.txt` in the prompt and let `frame(t)` move or light it.
  The same checks apply.

## Don't

- Don't run model code before it passes `check.py` and your own reading.
- Don't render the video before checking stills. A long 1080p render takes minutes, while a still takes a second.
- Don't put API keys, local paths or private prompts into a caption or a post.

## Files

- `scripts/ask.py`: sends a prompt to any OpenAI-compatible endpoint, saves the answers and code, and logs usage and time.
- `scripts/check.py`: a static check of the model's code (AST).
- `scripts/frames.py`: runs `frame(t)` in a child process with restricted builtins and time limits, and checks the shape.
- `scripts/render.py`: draws frames to PNG stills or an MP4, in mono shading or one colour per character.
- `scripts/photo.py`: turns a photo or image into ASCII frames, with optional colours and motion.
- `scripts/stats.py`: adds up the numbers for a post.
