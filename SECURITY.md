<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Security Policy

## Versions that get a fix

OpenBook is early. A security fix goes to the newest commit on the default
branch. No older version is maintained.

## How to report a problem

Report a security problem in private. Do not open a public issue.

- Best: open a private advisory with the "Report a vulnerability" button on the
  Security tab of the repository.
- Or write to the maintainer at stivenagostingjekaj@gmail.com.

Say how to make the problem happen again, which commit you used, and what you
believe the effect is. You can expect a first answer within a few days. Your
report is named in the fix unless you ask to stay anonymous.

## What is in scope

OpenBook reads files that you give it: EPUB files and TOML configuration. An
EPUB file is a zip archive, and a zip archive from another person is data that
you did not write. A fault that lets one of these files read a file outside the
project, write a file outside the output directory, or run a command, is in
scope. So is a fault in the speech engines that OpenBook calls, when OpenBook
calls them in an unsafe way.

## What is out of scope

OpenBook runs with the permissions of the account that starts it. It reads the
files you name and writes the audio you asked for. It is not a sandbox, and a
report that it is not one is not a fault.

The speech models are downloaded from other places and are not part of this
project. A fault inside a model belongs to the people who publish it.
