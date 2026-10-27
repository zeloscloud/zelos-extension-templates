# {{ name | replace('-', ' ') | title }}

{% if description %}> {{ description }}

{% endif %}A [Zelos](https://zeloscloud.io) agent extension.
{% if repository %}

## Links

- [Repository]({{ repository }})
- [Issues]({{ repository }}/issues)
- [Zelos Documentation](https://docs.zeloscloud.io)
- [SDK Guide](https://docs.zeloscloud.io/latest/sdk/)
{% endif %}

## License

MIT License - see [LICENSE](LICENSE) for details.
