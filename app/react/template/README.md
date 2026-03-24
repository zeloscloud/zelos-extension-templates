# {{ name | replace('-', ' ') | title }}

{% if description %}> {{ description }}

{% endif %}A [Zelos](https://zeloscloud.io) app extension.
{% if repository %}

## Links

- [Repository]({{ repository }})
- [Issues]({{ repository }}/issues)
- [Zelos Documentation](https://docs.zeloscloud.io)
  {% endif %}

## Development

Freshly created projects include a ready-to-install `dist/`. After editing source, rebuild before packaging or reinstalling.

See `CONTRIBUTING.md` for local development, desktop integration, packaging, and debugging notes.
