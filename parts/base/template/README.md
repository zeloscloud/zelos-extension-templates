# {{ name | replace('-', ' ') | title }}

{% if description %}
{{ description }}
{% else %}
A [Zelos](https://zeloscloud.io) extension.
{% endif %}

## What it does

{% if with_agent %}
- Streams a simulated sensor to Zelos: temperature, pressure and status in
  `{{ project_slug }}/environmental`, voltage and current in `{{ project_slug }}/power`, and its
  own log in `{{ project_slug }}/log`.
{% endif %}
{% if with_tab %}
- Adds a tab that shows the extension's name, ID and version.
{% endif %}
{% if with_panel %}
- Adds **Example Panel**, which shows the latest value of each signal you drop on it. Click a
  value to copy it. Its options set the decimal places and add a column with each value's producer.
{% endif %}

## Quick start

1. In Zelos, open **Extensions**, click {{ name | replace('-', ' ') | title }} in **MARKETPLACE**, and click **Install**.
{% if with_agent %}
1. In the Explorer's **EXTENSIONS** section, click the gear icon on {{ name | replace('-', ' ') | title }}, check the
   settings, and click **Save & Start**.
{% endif %}
{% if with_tab %}
1. Open **{{ name | replace('-', ' ') | title }}** from the `⌄` menu in the rail.
{% endif %}
{% if with_panel %}
1. Click **Add panel** in the timeline toolbar, choose **Example Panel**, and drag signals onto it.
{% endif %}
{% if with_agent %}

## Configuration

| Setting | Default | Description |
| ------- | ------- | ----------- |
| **Sensor Name** | `sensor-01` | Unique identifier for this sensor |
| **Sample Interval (ms)** | `100` | Time between samples, from 1 ms (1 kHz) to 1000 ms (1 Hz) |

## Actions

| Action | What it does |
| ------ | ------------ |
| **Set Interval** | Changes the sample interval while the extension runs. |
| **Get Status** | Returns the latest readings and the status. It stays out of the action pickers; Zelos AI can run it without asking first. |
{% endif %}
{% if repository %}

## Links

- [Repository]({{ repository }})
- [Issues]({{ repository }}/issues)
- [Zelos Documentation](https://docs.zeloscloud.io)
{% endif %}

## License

MIT License - see [LICENSE](LICENSE) for details.
