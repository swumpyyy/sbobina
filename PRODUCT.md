# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Italian university students (Scuola di Economia e Studi Aziendali): the owner and their classmates. They already have lecture recordings (phone voice notes, recorder, Teams/Zoom exports) and want study notes they can copy by hand into a notebook, read on screen and review before exams. Courses seen so far: Diritto pubblico, Diritto privato, Matematica, Economia aziendale.

## Product Purpose
Sbobina turns a lecture recording into accurate Italian study notes: transcription, revised transcript, notes with tables, diagrams and concept maps, teacher's exam hints, glossary and review questions, plus a check of the notes against the transcript. Success: a student drops in an audio file and later gets notes they trust enough to study from, without paying anything.

## Positioning
Free and fully local: transcription with Whisper and note writing with an open-source model through Ollama (an in-process MLX engine is planned), all on the student's own computer. No account, no API key and no per-lesson cost. The audio never leaves the machine. Claude (paid API) remains possible only if someone explicitly configures it.

## Operating Context
- Runs as a local web app (FastAPI + static HTML/CSS/JS) at localhost, started from the terminal; also has a CLI.
- Long jobs: a 60–90 minute lecture takes many minutes to transcribe and write. Students leave it running and come back.
- Optional course materials (slides PDF, images, text) improve technical terms; the glossary of each course grows lesson after lesson.
- Exports: PDF (printable, to copy into the notebook) and Markdown.

## Capabilities and Constraints
- Three outputs per lecture are all required: a PDF to copy by hand, on-screen reading and review, and concept maps with review questions.
- Must stay free: the default AI is local (Ollama, model gemma4:12b); there are no paid defaults.
- Hardware reference: the owner's Mac M1 Max with 32 GB. Classmates' computers are unknown and may be weaker.
- Language: Italian UI and Italian notes.

## Brand Commitments
- Name: Sbobina (from "sbobinare", to transcribe a lecture).
- Binding visual direction from the owner (2026-10-13, replaces the earlier neumorphism/hi-fi direction): **glassmorphism with blue and white accents**, professional finish, polished fluid animations.

## Evidence on Hand
No testimonials, user counts or benchmarks exist. Do not invent any.

## Product Principles
1. Free and private first: nothing in the default path costs money or uploads audio.
2. One clear next action per screen; long jobs show visible, honest progress so the student can walk away and come back.
3. Accuracy over polish: uncertain passages are marked, never invented.
4. The notes are the product: reading and printing them comes before decoration.

## Accessibility & Inclusion
The owner asked for an ADHD-friendly experience: minimal distractions, one step at a time, visible progress. Glass's low-contrast tendency must not reduce text or control legibility (WCAG AA for text and focus indicators).
