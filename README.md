# CaptainCredz2

## TL;DR

CaptainCredz is a modular and discreet password-spraying tool, with advanced features such as a cache mechanism and a fine-grained timing control.

## Quick usage

```
$ git clone [...] && cd captaincredz
$ podman build -t captaincredz .
$ podman run -it --rm --network host -v ./metadata:/metadata -e TZ="Europe/Paris" -e DEBUG=0 captaincredz
```

The `metadata` folder should contain the following files

```
metadata/
├── config.json     (mandatory)
├── passwords.lst   (optional)
├── usernames.lst   (optional)
├── userpass.lst    (optional)
└── ww_config.json  (optional)
```

## Developing a plugin or a post_action

```
$ podman run -it --rm --network host -v ./metadata:/metadata -v ./app/plugin/plugins:/app/plugin/plugins -v ./app/plugin/post_actions:/app/plugin/post_actions -e TZ="Europe/Paris" -e DEBUG=0 captaincredz
```

You can mount the `./app/plugin/plugins` folder of this repo to `/app/plugin/plugins` in the container (same for `post_actions`).