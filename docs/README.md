# Delphic AI Documentation

This directory contains documentation for the current Delphic AI application.

## Current Application

Delphic AI currently runs as one Flask application with three connected views:

- Home at `/`
- Math tutor at `/#tutor`
- Science tutor at `/science`

The Math and Science tutors share navigation, themes, session controls, response streaming, transcript downloads, and responsive UI behavior. They use separate prompts, learning controls, routes, and conversation histories.

For the complete current feature list, setup instructions, routes, project structure, testing commands, and known boundaries, see the [main README](../README.md).

For a simple explanation of the Mac and Windows launch files, see [Running Delphic AI On Mac And Windows](RUNNING_ON_MAC_AND_WINDOWS.md).
