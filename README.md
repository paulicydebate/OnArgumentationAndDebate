# On Argumentation and Debate

An open textbook for introductory Argumentation and Debate courses, by Paul Villa (Diablo Valley College). Draft edition, November 2026.

**Read it:** https://paulicydebate.github.io/OnArgumentationAndDebate/

## How this site is built

The chapters are written and edited in Google Docs. To update the site, each chapter is exported as Markdown and rebuilt with `_tools/build.py`, which:

- turns each chapter into a page with a chapter list, an "In this chapter" menu and previous/next links;
- places each figure with its caption and alt text;
- turns the check questions and their feedback into self-check quizzes (nothing is recorded).

The site is plain HTML, CSS and JavaScript, so GitHub Pages serves the files in this folder as they are.
