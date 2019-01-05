# Mas2tter - the Mastodon-to-Twitter Mirrorbot

This Python3 script loads the latest Toots from your Mastodon account and posts them on Twitter.
Some formatting is done to keep the content of Tweets in 280 characters, possibly posting two Tweets.

You can choose to either link to your Toot so others can click through to your Mastodon profile (see screenshot below) or use the alternative plain text mirror. The config parameter `link_to_mastodon` is used for this.

Your Tweets will contain some of your original Hashtags. Set the config option `tags_to_append` for this.

![demo Tweet](example-post.png)

## Setup
Fill the config values `api_base_url` and `user_base_url` as given in the example. The API base URL is most likely the root domain of your instance, the user base URL is a simple text string which is used to check Tweets that contain Mastodon URLs to your Toots. (Better have a look into the code, it gets clear there)

## Changelog
Versions `<v2.0.0` do not use the streaming API, but instead regularly pull the latest Toots made by a user and compares the locally saved Toot ID to find out, if new Toots were posted. If yes, they are cross-posted to Twitter.

Version `v2.0.0` introduces the usage of the **streaming API**, meaning that Mas2tter listens for new Toots and acts based on events sent by the server. The old pull script is still available in `sync_existing.py`, it can be used to sync existing Toots which will not be seen by the stream listener. Please note that the script uses the old-style formatting.

Version `v2.1.0` introduces **multiple Tweets**, if the character limit of 280 characters is exceeded. The Toot is then split in half (based on spaces between words) and two Tweets are posted.

Version `v2.2.0` introduces **command line arguments** to use different config files and to enable debugging output. Exception handling was extended to hopefully handle more connection errors.

## Libraries and tokens
This bot uses [Python-Twitter](https://python-twitter.readthedocs.io/en/latest/getting_started.html) and [Mastodon.py](https://mastodonpy.readthedocs.io/en/latest/). To set up the needed access keys/tokens follow the instructions there. Mas2tter has no running public instance to date. If you do not have the resources to set it up on your own, have a look at [crossposter.masto.donte.com.br](https://crossposter.masto.donte.com.br/) ([Github repo](https://github.com/renatolond/mastodon-twitter-poster)).

## License
This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

More in `LICENSE`.
