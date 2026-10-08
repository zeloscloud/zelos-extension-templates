# {{ name | replace('-', ' ') | title }}

{% if description %}> {{ description }}

{% endif %}A [Zelos](https://zeloscloud.io) extension.
{% if repository %}

## Links

- [Repository]({{ repository }})
- [Issues]({{ repository }}/issues)
- [Zelos Documentation](https://docs.zeloscloud.io)
{% endif %}

## Getting started

```bash
just install    # install dependencies
just check      # lint and type-check
just test       # run tests
just package    # build and package for the Zelos marketplace
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development and releases.

## License

MIT License - see [LICENSE](LICENSE) for details.
