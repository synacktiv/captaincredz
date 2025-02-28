# CaptainCredz

## TL;DR

CaptainCredz is a modular and discreet password-spraying tool, with advanced features such as a cache mechanism and a fine-grained timing control.

To start using captaincredz, the following lines may be useful:

```
TEXT_EDITOR=nano

git clone https://github.com/synacktiv/captaincredz
cd captaincredz
pip3 install -r requirements.txt
$TEXT_EDITOR config.json
$TEXT_EDITOR ww_config.json

python3 captaincredz.py --config config.json --weekday_warrior ww_config.json
```

## Installation

Captaincredz can be installed with `pip(x) install .`. Alternatively, one can install the required dependencies and run captaincredz via the script `captaincredz.py`, by following the commands in the TL;DR section above.

## Usage

```
usage: captaincredz.py [-h] -c CONFIG [-w WEEKDAY_WARRIOR]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Configure CaptainCredz using config file config.json
  -w WEEKDAY_WARRIOR, --weekday_warrior WEEKDAY_WARRIOR
                        Weekday Warrior config file. Only active when specified
```

For detailed information on the format of the configuration files, please refer to the [wiki](https://github.com/synacktiv/captaincredz/wiki) associated with this repository.

## Extending CaptainCredz

### Writing your own plugin

If your identity provider is not yet supported by CaptainCredz, you may have to write your own plugin.

The best thing you can do is look at the plugins already implemented, and write your own in the same way. In particular, adapting Credmaster plugins to CaptainCredz should not be too difficult, as the functions defined are the roughly the same.

### Writing your own post_action

Maybe you want to add an action after each success, like sending a Telegram message for instance. This is not yet implemented by CaptainCredz, but can be implemented fairly easily in the current state of things.

The best thing you can do is look at the basic post_actions already implemented, and write your own in the same way. Post_actions receive a variety of data from the plugin in order to implement their logic.

## Acknowledgements

Captaincredz is heavily inspired by [CredMaster](https://github.com/knavesec/CredMaster). We figured it lacked a bunch of interesting features, such as a cache mechanism, more generic `post_actions`, or the ability to replace the integrated Fireprox IP rotation implementation with our own [IPSpinner](https://github.com/synacktiv/IPSpinner) proxy for example. As such, we initially performed a [pull request](https://github.com/knavesec/CredMaster/pull/80) to the original CredMaster repository. This pull request brings major changes to the project's core, as it was not initially intended for these features. Therefore, in parallel to this PR, we decided to start a complete rewrite, carrying the good stuff from CredMaster while incorporating the things we needed. The architecture of the code is modular, and allows for future additions.

Big thanks to [@knavesec](https://github.com/knavesec) for their work on CredMaster !
