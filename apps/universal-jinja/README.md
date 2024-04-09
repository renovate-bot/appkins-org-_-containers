# jinja - Docker mod for any container

## Custom configuration file templating

This container supports jinja2 configuration file templating using [mattrobenolt/jinja2-cli](https://github.com/mattrobenolt/jinja2-cli).

| Name             | Default                    |
|------------------|----------------------------|
| JINJA_TEMPLATES  | `/config/config.xml.j2`    |
| JINJA_SEPARATOR  | `\|`                       |
| JINJA_DATA       | `/config/data.yaml`        |

## Dynamic custom environment configuration

This mod adds configuration templating with jinja.

In any container docker arguments, set an environment variable `DOCKER_MODS=linuxserver/mods:universal-jinja`

If adding multiple mods, enter them in an array separated by `|`, such as `DOCKER_MODS=linuxserver/mods:universal-jinja|linuxserver/mods:universal-mod2`
