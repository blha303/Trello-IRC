Trello-IRC
==========

Created for [Puzl Inc.](http://puzlinc.com), made open-source with permission.

If you use this with your company boards, please drop me a few dollars via Paypal (b3@blha303.com.au) or email me for other options.

Trello board for this project: https://trello.com/b/AAji4Yjn/trello-irc

Trello credential generation
----------------------------

* **API key**: Log into Trello as a user with admin access on the desired board, then visit https://trello.com/1/appKey/generate. Don't use the OAuth token on this page, it doesn't work.
* **OAuth read-only**: Substitute your API key into this url, then visit it as the above admin user: `https://trello.com/1/authorize?key=API-KEY-HERE&name=Trello+IRC&expiration=never&response_type=token`
* **OAuth read-write**: As above, but with this url: `https://trello.com/1/authorize?key=API-KEY-HERE&name=Trello+IRC&expiration=never&response_type=token&scope=read,write`

If you have any questions, [create an issue](https://github.com/blha303/Trello-IRC/issues) or email me at b3@blha303.com.au.

