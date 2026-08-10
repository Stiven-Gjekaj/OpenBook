<div align="center">
  <a href="README.md"><img src="assets/openbook.svg" alt="OpenBook" height="44"></a>
</div>

# Getting help

## Read first

- [README.md](README.md) says what OpenBook is and how to start it.
- [docs/configuration.md](docs/configuration.md) explains every key of every
  file. The examples in [examples/soultale](examples/soultale) carry a comment
  on each one as well.
- [docs/architecture.md](docs/architecture.md) explains how the stages fit
  together.
- [TODO.md](TODO.md) says what is not built yet. Look here before you report
  that something is missing.

## When the tool refuses to run

OpenBook writes one line for a problem that you can correct, and it names the
file and the key or the chapter. Two of these are common:

- **A speaker code with no entry.** A chapter uses a code that `cast.toml` does
  not have. Add the code. The message names the chapter and, when one is near,
  the code you probably meant.
- **A key that nothing reads.** A key in a configuration file is spelled wrong.
  The message names the key next to it.

`openbook check` reads the configuration and the book, and says what is not
finished, without making any audio.

## Ask a question or report a fault

- Look through the
  [issues](https://github.com/Stiven-Gjekaj/OpenBook/issues) first.
- Open a bug report for a fault, or a feature request for something new.

Say which commit you used, what you ran, and what happened. A short piece of a
chapter that shows the problem helps more than a description of it.

Do not use the issue tracker for a security problem. See
[SECURITY.md](SECURITY.md).

## Help with the book, not the tool

OpenBook reads one book format. A question about a different book is a question
about writing a new grammar file, and
[examples/soultale/grammar.toml](examples/soultale/grammar.toml) is the place to
start.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
