from __future__ import annotations

import base64
import hashlib
import os
import shutil
import sys
import zlib
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.3"
TO_VERSION = "0.13.4"
PATCHES = [{'path': 'app.py',
  'old_sha256': 'c4698dcd7f2548815e9474ed349cf21a03e97bf5487f8a9ba6e055d71a797d1d',
  'new_sha256': '8471097af7a0d1934520db50aa46bb2bf6d92af208845759566c37e27decdf44',
  'ops': [{'i1': 25,
           'i2': 26,
           'old_sha256': '70eb63602bd52c80483ba250d43a9ff491036f13e6d2e5f22fa47a97ae6616a6',
           'data': 'eNpzDAiID3MNCvb091OwVVAy0DM01jNR4goI8vdydQ6JDw5xDAkNdg0GymkoBeVXFRQlJueXHV6Yl6+ko6DknaqQnZ9XUpSfkwriRkE5CAWuFQX5RSVQviaXa0SAf1BIPNBwN08fqKHeED15h9cqaGTn5xbkpJYA2Zog3WGH92YnVikUFOUr5CdlpabkHV5Yll0KNAcAj309xg=='},
          {'i1': 1253,
           'i2': 1254,
           'old_sha256': '9353fba800924bfcc7ea80e25485cc005cc9147432e8053c936d7015e075d78e',
           'data': 'eNpTUMAEpQUpiSWpKfGJJQohrhEhCn7+QBzq46PDhUWxQnFJYklpMapKBRdXN8dQnxAF9aD8qoKixOT8ssML8/LVuQBnjBw8'},
          {'i1': 1341,
           'i2': 1341,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNplj19LwzAUxd/7KQ55WQuj4OvAh2irL9kmpQVBpGTdrUa6pDSZG5Z+GD+LX8zGP3PFA4FcuOec3wW+1XbmhSpXHqR2tMUl+gBnYtZJt7dsAZan9zlW6/EVQiBJb3ghcswy89Z2sjKvH+/azNj8ZB9Ov4Nyz7DU1HFltB7bwgjSYhwWkzI6KuuUfipbz9E9XDyiNh06KO2XYzpStXcUsruM3y45nNw0VCpdm/DnDBuxaJhk+gAtdzTHlqrGJ00vjpWjnQ2jKYmXqr+M0MZ52x/c/1Wvc8CacZGnGXJ+JdLfQgueJLhei2K5Qu+jB/QeamBREHwCWE1yQg=='},
          {'i1': 1440,
           'i2': 1441,
           'old_sha256': '2d6d006a3c2f50f49b5dc1f51512db3a0bd25128cb1701ce03d50314803a8200',
           'data': 'eNpTUEAFSsGuPq7OIQopelo6BXp5ibmpCgVF+VmpySXxIA5QrLgksaS0GC4K5boF+fsqpKQm56dk5qUXK6QoePl7+sEUAVUr+AN5epkptil6MJ2ZKQrhHq5BrkC7gOL2SjpcAJsiLAM='},
          {'i1': 1700,
           'i2': 1701,
           'old_sha256': '5386b57907d7f8f6dce818d4c76f5c6ab1ff8d1d0064c2026d38882651688879',
           'data': 'eNpTUECAYFcfV+cQhQK9zBSdAr28xNxUIFVcklhSWgxkJBelJpakpsQnlgA5pQUpMA4XAGUfFJY='},
          {'i1': 1821,
           'i2': 1821,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqdksFOwkAQhu99ismedpNK4pWkEqI1xqgQCngwplnaaVisu83uFpC34UH0Qnwvt1BoIBzUObW70////pl64CrFDAqtZpjY2FhuS0MN5pl/OBRpG4S0DC6uwFjd9qCuhbBTqHpbiZLStVIG3IB7aXqq0moBQXXcwiUmpUVKovAhvB7Czg9uB73HvZ2B57twEIJIgw7xgTpn2pAwn7FWhjaZKomUHWzmPC/RmTg+6uxeyE6ZvILSQAZqVWieqPlmLRVhILItE+YGgZCDiEZballruZ76QUJ/0Lt3uHE07A5HURjVXx7Let5+mgZt/JuJ+nX+doXNmpnVUwlAKv3Oc7HC2BQ8QSezvWliO8i6WSp7jvRkEVw47nEVK9RaaUqesMi5lZvPSmcO/C3BFmF/3rDjqADOrfjy/9s99jgfYPwx0Vxu1lt0KL+/YA4pt3yyWa8ESMSlMLacHaWq6gh11L/pDsOGMQr3v2bQ8aEsnCCmMbdB5wR/1+RDLNUiFkZR5sNJJMa8HzGsEZk='},
          {'i1': 5961,
           'i2': 5961,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUICA/Lz4gqL8rNTkkvjiksSS0uL45IzEvPRUKwX/gpLM/LzEnGjnxJycxKSc1OjozLwSHYXikqJYHQW//LzU2FgFWzBDhwsAL9Qa4w=='},
          {'i1': 5968, 'i2': 5968, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4tScNL38vPiCovys1OSS+OKSxJLS4vjkjMS89FQFWwVcUlwAzf4XVg=='},
          {'i1': 6022,
           'i2': 6023,
           'old_sha256': 'b33a7dc302c0aa01cd0ed5fc66d607c30eb8e42b415740682045b1f1c3d4b363',
           'data': 'eNoljUEOgzAMBO99heUTSBE/yC/6gTRZCpQkKDbk+3XLXnZXGmmI7gj2eTpa3RBVyJPqZ3o24FrRh2NuIcNRrPuZi/iBi312LBr0FBspKP6NWBOSrYZLeHQkS+2eF4S0lrchP5M5smGeX612AY+PL6VCLHQ='},
          {'i1': 6024,
           'i2': 6026,
           'old_sha256': 'cd05f57c6258405d669a89a3c09ef94cd16f87353945ba5ac160ee3732faed9f',
           'data': 'eNpVjj0KAjEQhXtPEaZSSLOrCx7AWgTBPmReFTcLSczC3mYPIBbWVsF7OUFBne7xvZ9R6ntL8qYHadqXeUJWxllR7abTNNJKC4/JpEsUxzGZTLppWk0WPiG8OZuEindi61UuDxcQnzdxrj8lC/U3yLADgyVyGOIZ7MtVMVy585DLLEqiP/sBudafECb5rNtqQu18AYhCOac='},
          {'i1': 6043,
           'i2': 6043,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpljs0OgjAQhO88xcYTJIQHIOnBGDyY+BPBc7PQbYK21NDC8wu0qNE9bXZmdj4AP9ahGyzX1A3AwD2y47TFlpTMnr25U+MWLQVH2Bsp2R6VpSQKcZCmB+6fQNvB5Xo+FLuKl9W2upVFmb+NP2UZCsEbozV2IlZYk2LhTQrhzBTqWuCUWqUcFjBuyfGVziuxdckH6g/ft6FtUFBo25xwio6tm6nGTQqzj30RJtELksRiZQ=='},
          {'i1': 6153,
           'i2': 6153,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqVUlFugzAM/e8pLL5AqnKASv3cCSbtqxIK4JRsbYJid6ObdpBp19nutQQKGYNWWj6IbPyen18MAFChgpyQ88bZRyw5J5Z8opTwoNbQBxt/u2yzgsvRCoxlCCXCfzwKqxGvq1gYzhGJ5B4L2wqq7Ys2yqbJPctnkE8lJmtIHs4FOsYQa+ETjXRoeBvoswmVQz45M6ZiR9iCNpxeExRZ2J2n6jpIJVkWklAs+BBZBjciG7YlNgx33aWtAUkhd3N+dM66qQGqjwjBYGMr+f2hDxZej1+fRrPYmZ1586zv/3DGP1A3mDV/xsnLWpo9ThXOTBmNuYa/6cqSM3P+RhKtJs1yh8oh1UNLSrPZQMMvga0mX+H38peWLFt43BHSL4YXE9Z9hpwD4+iXjfJ6Vj99zP4E'},
          {'i1': 6230,
           'i2': 6231,
           'old_sha256': '7ea25fe3b77563f60bda42f206734650425bcdaa483fba2e366d21ff6a2c770a',
           'data': 'eNpdjEEKwkAMRfc9RchKYU7jVkoIkyAD7aRM0orexrN4MetAF/pXH95/H+A37YqVZ8UxfasHx+o4gjXAiz2Xxtm296sadi6N76XeSDj0mGEa/j6BpPgy8aPvosx62t2JPUg0m6gQx2Gf+3HTrXixStnWurM0fABKwzOm'},
          {'i1': 6459, 'i2': 6459, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiK4XikiIFWwUlJS4AUX0Osw=='},
          {'i1': 6643,
           'i2': 6643,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNp9kF2LwjAQRd/9FUOeUghFBREW8iQVBEFRWQRZytRONRhNSEc3/nvrKusH7M7jZTj3cAFux7xLx1iQlTXZKqXoXeB8E9zRK2CKrEUW12Q/RJJ6XO9kbUrSwlLFQoHHMmrZVtBLktadCM8gH1xlLOUnDKCh6ZpzMIfNJwZ5QnsknS2nk9kin84mw9E4m6/aXw/Q1W3g9oUrXJS/6XvF3bVm5EYsEJbuYM/iZt/0Giws6T+k1Av2R6l+d1LwbUre6m7n8f3vGP1mjAsCz2wP'},
          {'i1': 6661,
           'i2': 6662,
           'old_sha256': '48fd42f08073efe299aee53188e08e6c6d505016205a881a877ee08d92f66bbc',
           'data': 'eNqNUktOwzAQ3fcUlleJFEUtUiWE6kpQ2gUqatUUNghFju2mJokdOZN+dhyCDYfgFIiLcBKcppQCVcGr8XjeZ2aMUH0oA6lVaGQ8B0QQJP7A0Ew427xUShgPRTEpRDrze6PhaBLcYUYNx/duAx1g8WMjuWP0kjQ9xHRaZoqceKgAyZI1wQJ7KKd8RZyWzTbdLxKw4kMaidTZp/MQiBUQHABdnOGKZ50Kgq9LENyfbuqx6+eUJU4huX1JxQx2GtZCe09i08SWvQAKZREuqKn7DsBIFd9S4yxoWlqi98cnfBTKdBbpCmzRvSqO9MrZAX7OpbJOwfJyWdAoFRzXrVkDsrqTw+Y8tLFTkPFkdNXvTcNgej69CfqBh5aSw5y02t5O82+7xyZ16v4DH0nFHdzpfDYciFQwu4tut1pOhQrZnKpYhKw0RigIc6MfbMmW5vu+L0oArQ4ufARi8fb8+gJofDlANGHVz7EeMqp4PatQ50LtZLhmZWaD4vdvcBsfLZb11w=='},
          {'i1': 6959,
           'i2': 6959,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUECA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVuIbEpiSWJSYnGqHqq0BoybmaLJBQBiRhzl'},
          {'i1': 6978, 'i2': 6978, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUEAFxak5aXrJpUVFqXkl8QVF+VmpySXxxSWJJaXFCrYKSkpcADN1DgA='},
          {'i1': 7057,
           'i2': 7057,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNp1UktOw0AM3fcU1qwSgXqASiwQ6gYWRWlZITQyE6eZks4Ej4dSbsNZuBj5VGlTtd5YY7/n52cNQB+fESsre7iDQFUx1Ye3DnG7Rd4n6eQABFv0EBOZyYmu2W/IiLY5oMvBMKFQPhvwbWAUr4OgxNAoqCeCD++EfUWqnZcc1F5VdIZY0Dr1Bp5hqOe2KKiRMxTOOsFHNqR3yM66ddNNgapAoDL/UzMa//X367warSO8H+/XRmcqR8F3DDQNdHTWL55ccX176i69PPacNZzihHqZqZkKplBqNGK90yVhTpyMdejbUC0w71KDAgxt7YpHXfl1op6zxeP8YQXL1f3qZQnzLFtkM1BwA0w1Jw09PYp0PCyEuDFcUX8KHUq/O/8o6eQfGVm7/w=='},
          {'i1': 7423,
           'i2': 7423,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqNVV2O2zgMfu8pCM2LgwZGEmyLRQA/TNMMFgV2J8ikP0AQCLJNJ2psySvJSWbu0EPMAfYI7cu09yplp42dTtsVAsSiPn4kP9IyAECKGfBCmC0vjX6PieN4KLVxmAYW86w3fgLHJTNQ2oG3hkllDCr33UemJ5xfBl1l1HeTM7fd85okFU7EwmJo8cRknXCVDX4SpQ9sWqendw/3SrPej6znTg0hRGeePzpyg5lBu+EicVIrvkGRoglOIfCQYOlgWv8RAoT1tkcq47leB2w2v341nSxg+m52PV/AzeJy8foGpvP59XwMDJ6SSqUJiKHXe1Jz1L1o5OfaUHB+yO2h1qIPpXCbMVhnWi3Zx1TXW222sdbbVqZ7X+8+Dn0lO2yZQyddjl6MNw8ft+IOSCXQ8XtM1cP9bluxNlaUJao0WLLrOyU+f0D18B+jBvyt9JdP1u2Ou1dsdQq8NroqMR1DKhO3dFWZ45JS7vu8V33Ici3cisJTpaLKnUcFtfFEkWkDBqQCzDKs8+eE0IYbvbc8M7rgVlcmweOQHDe9bhtStHKtRN2miObWFCKXd8htKbynCfFA4nAlCgQfMDRiX++6E3Wc+TZbjf7X3YK08I9W2I3rV6KVk6rCzsFRmWXQ4up7pkoQ2t3ySknnydnWst4KnkaNWkEdrCtPl8M79vpQp6TANu/uMVwoHRY2oOMt3ka5KOJUwGHcEoTswWE5WNGvd6ZhawQ6ASlSE3XVTSvBPPcp7O1yuOpS+aMwI12oGVf0F3ipIzahHGIjaY4s5RINB32IdZ5GC1Nhn3TMtYnYVb3OXvWGUFLACGbCOTTqinYBszqXKRFm60njPrh6Pnnx8jF3Cr5WBdZJXX57DjbayDtKUeQRS8iAhth2aJxMWqazedX7pnCvdzOpQSGVf4hGZ6q2laLzR8bnf2t1FGj452g4OheIqKkLoaqKmDLKfL89IRuEFxcXndecWKpC8VRS+ZYabJfskq3CvUzdhjyejX4DftECD//4DXjSBg/aYLp7keaxFArr2/py1L2MKqc5NZz0Demi9vebDU/MbajdYPNBKX3X0IalWOMNutflzNDMuIWekYEY/Ji1HT2O08eoKhvY22+J/gr0F8r1xkvbqiYOrdhh4K9sutq/AlY6RMg='},
          {'i1': 7435,
           'i2': 7435,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUICAgqL8tMycVAVbheLUnDS91IqC/KKSeKhofFlikV56aomGpkJmmkJGYnFiSUmRBkihjoISplIlTYXUnOJUBdeIAP+gkPiAIH83Tx/X4GiDWC6obQr5RSmpRfEQrUA74bbbKiiFHd6bnVgFElLIT8pKTck7vLAsu1SJCwDkmjm3'},
          {'i1': 7436,
           'i2': 7437,
           'old_sha256': 'a752975ea24224285233e3eaafa5923e76aaf4543fe3cc9cb048687feee8fe38',
           'data': 'eNpNy7ENgCAQRuHeKf5Qu4KlcxiUM0EIZ86TGLdxAEewYjGjjb76fcCXeo3UmHabWZSzVeRyBbtjFgb3E7lUjhxWAz+CxZF09L6guBD+MHBS4ZjK+eCJgsIx2m2guJq6ugGHDirj'},
          {'i1': 7438,
           'i2': 7439,
           'old_sha256': 'dacaecacf94dd8cb86bba1eb9d8a40d86b75ef9c5fc13866a5384c84934a892d',
           'data': 'eNpTUECAzLzMkszEnLTMnFTbNKXq4sS01FoFXYX8pKzUlLzDC8uyE/UqcoorlBQy0xTyi1JSi+JTKwryi0oUUnOKUxWQdJQd3pudWFUJUa3DBQBqGiK2'},
          {'i1': 7445,
           'i2': 7445,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUECAzDSF/KKU1KL41IqC/KISKy4FNFCcmpOmB5WNhyityCmu0ChILMnQxKE6N7EoO76gKD8rNbkEqjU1RQOH6uKSxJLS4viyxCK94tQSjTSlsMN7sxOrFID6FfKTslJT8g4vLMsuVSjNyT+6LzXPSqEaZHWtEqZxRaklpUV5XFwAI6FCrQ=='},
          {'i1': 7615,
           'i2': 7615,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUEAFGkrBJYllConZyalKOgrFqTlpesmlRUWpeSXxBUX5WanJJfHFJYklpcUK+UUKSo8apihp6nABAHLVFPk='},
          {'i1': 7957,
           'i2': 7958,
           'old_sha256': '145b7bf0334e3deb6f3a17770535e2aa7e4708d52ed4102835b116d1113ed04a',
           'data': 'eNpTUECA4tScNL343MSi7PiCovys1OSS+NSKgvyiktQUDU0uBXSVxSWJJaXF8WWJRXrFqSUaaUre+XklRfk5eYfXKrhWJKfmKJTm5B/dl5pnpVBdkFiSUaukyQUAWaMkng=='},
          {'i1': 8058,
           'i2': 8058,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqlVs1S40YQvvMUE11Wqnhd5Jai4mwMayosIFNeoCp4XSohjbDK0gzMjGxsisMec+C+tXvimAOPwF6E3yvdI8n6wWyyiS7qmemvf77uaYkQQn6TylWhF1M15v4GbBCfBsQRfOYwSn3pxC5L3MgRdBrSmQn7W2SbuvGAzyzy+ldyznm0pXH4KHqtSIcwLmI3ChfUmdA5YtroJZGEC2IY1kp95goWsgtH8QllEoDm6ggfY+f3P7bTO6OVSXso2L3+6dPn5aee3S+WvUG+ONvv28eD/kH/tHucHb7be3+c/lnKPaNV92D3zuz042GmcWZ3tXSa3u30yGF/+Wjr5Z5endmZVvr56CAXT3KpvzMgu92Dg+3uzn7FQ5mooCoRjLhsbupcScgyrgJgZLVTp8NCtjR5HmdB6FPmURJKIFcRmzMK1nwSRNxVDSWL/EI22z9vWhtlPa+ghqGaOzKJY1fMTUmjQNfPDz01lEq0IAA1KisJJrEgNAiop8IpdcATF9gX0gkEjx3JE+FRqS2180WZcBjoOFF9q8Z4bncodOpSeJh41QZCYbs9CSE9ODMN7RlpzoM3LI0VGgmaaHK0cpIAA0K5cNYhADB/KpW1bzSP7l5ucatMQ7vGeCUXivrmjWjrrec2iwMsSiEjAzqDNxj9+5PD9OPyUy52B4Z12yJwPzoMroYA/xnDsFP6l96Y+klE/z1jnQ7JCfsWSb5wZ9Bp/99sbshpmA+hbQT2InK3WdKJzGlqAJ5xW+8OSNebIMbj8aUrqFPYL4ioDwh8hpVirOiqFAQi18KoVVMtGFinWfNh1VbVzH581mB5+HnzmyIfe/gSSs5CNTaN/r6hb/bawz17t29YVu0e4dCo1aG4Bi8VzvoHTrFW5nde7Nb3NEotwHoH/nc2XySzclt0PE4+RmVtAHwj7lxfX91VHj9AHuEFfMiobzyb4zf1j4jiyo2MLRJRhqMY2KqfJ8yNz8OLhCcStGL32txslcrkdTmzniPzA8Ct5IZOhUTQqqwaeg12QLexU+rfVr4ccgxzcu3no2yzK6RaD9WmYkndpeDnEY1B82pYyWuEdwF2qlkUe82Iy4s5pQI/XGDMeMsvuUie7ihzCb5Z+kAmnCnBI5fwBXPxKH30xiROH6RqG1j2IhgaSUqMbqJ4jH9Bk/S+xDKwuLwHYfk1vffBRIZK/4rbxiqQmErpXtBzft1GokIW8MY/zFrjjd+QwDjiEV9+nczJNH2cuItki9xcDV/pxno1uv3AjIb+O+qzLDn29IXgW1HGM1Sl3dZi95s80QKXF2U9KtNFmOALP32I5hmsUrm1wJNLvuACwkTolBy93c1wjepq7Ad2k5f2tkERTi6mOthl1R+sjb8B405n6w=='},
          {'i1': 8063,
           'i2': 8063,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqljsEJwkAQRe9WMewpgqQAwSZsYJnsTnRl3Qmzk4CeLMIGrMVOrMQkHkTNQfEfP/8/HsAzoYYtZlSVIlOsF2DQaeBks6K22TreV2zmyxm8pT8Oh9K1IpTUNsI7cmqD/9wOGcev7A6lzKTFJOexARYwaz42go676yX1Lt/iR/XScarDphUqhppWRgg9p3iYAFHM9LO9uZ3Of0v5kLGK5HvQHXBifSk='},
          {'i1': 8110,
           'i2': 8111,
           'old_sha256': '91e3fe6a5ffecd542b34cf486c844ea47213e6af026a8d6a4f68fe20f253511f',
           'data': 'eNpTUECA4tScNL34lMSSxKTE4tT4zJLU3PiU1JzUktQUHXTJgqL8rNTkkvii1LzEXDzyxSWJJaXF8ckZiXnpQGVcADstJ+o='},
          {'i1': 8112,
           'i2': 8112,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNqtUs1uwjAMvvcpLE6thPoASD1ME5cdtmllN6TItC7tBkmVGMaGkHiNadOeZnsRnmQJBMrfdsKKlMix/fmzvwCs5VSAyEqUQxLZRGuSLGqtnihjYRh5YkJDo6INNLVfya2SFHUC8FYVIBWDi4iPs6u8iXOmiSda7lyb4pBskjHjSkmPKKao4yFxGO0D+QSHV0m4f7i76V73RNq76j2m3fRfLNavh/9rzBwZB2goNnSW8xlGbd9FdFrt/PAcv/XjNGGPq20gLFop4xTwOSN4G39/SHtAIqyWX/NN6GK1/IxbDTTNMqoZuuvLTg/QON8h0zEZg0MaqFlsSvVCWisdNlCtNnhgQyCpVjn+vFcjtWmh4rgv+3Juqy5sZI2OYeK6j4Jgp57tHI+oe1XlXj97srD74+0kO/bWh4r6Y/aQJC4xbDxR5wJrEJoKTaYUXoIlYU46jC64sF9agyAg'},
          {'i1': 8160,
           'i2': 8160,
           'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
           'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVuIbEpiSWJSYnGqHqq0BoybmaKpkJmmgOAqpOYUpyooKXEBAAnBI8Q='},
          {'i1': 8213, 'i2': 8213, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVsFJSUuAAXtDQA='}]},
 {'path': 'README.txt',
  'old_sha256': '51e2141a20518bf020aa362e55607e332b3221fc13c480a6c3e7c9996ea04f6d',
  'new_sha256': '74ef98ea981d5759ccade377a20e3429c9350961a3aca229c9aa9c5236bde1e8',
  'ops': [{'i1': 1,
           'i2': 2,
           'old_sha256': 'fa86bd6adf4caaaa97fafef0733e1304df2b0a1a1b2344bbbd262905f90c07a3',
           'data': 'eNqtUrGO00AQ7fMVU4Lky4GgClV05KTguzjKhQiu23gXYq+9a9lr67IVfEAqqiOVyxRRCjqkpFn7R/gSZu0kOhAlkaXM7sy8nffezFiqGbzovnzVfd3pjLxZ9R1mA/wm98PjNfz68g3upv0Z9N2rgQODD2NvMh2ZFYwn3vXw5iP0of9+6t32p8Mr13wF1xtNJ95Nv3Px336dC3BJfaCmBMJ9BjEGmSJFDyZSJynxZWFKIeESXAZcCpXKiOHp/hif04OHRKaqPXY7AHcIAiGDIqDVWkEBlCgyN6UOIMDTIiKFMNsYJBfVGghEqFbIQkjzamVv4motAtXF+cYSBOJuYqCMmx+0ecNsIUnl55TEQHIlY6ICny+hWC4kFVLZtKxWTOFfJOsD4w6iY0YL0uDjhDZSTJi9v4D60ZSU1zvnXA+8HQWRTrSdU4SX2JNKTc02qnc4fZ5ILVPEtfXjt9ft3DynT6ZDZY/9BN8OKbMM5hEScxqCJRTNzjQ+JPUjsyVUNnbkOO8TA97AnGnQYVCXyr5pKZzAcB5d77BJsD89tDMNHnwWNSbTgtiWT0G07IF75gXPuIyTiCmMnyOxmdlzom0lyLlV0JQFzy3UvzPWcm1KdM+q0WpOc39h9j3wGvGZfeUSbgXKnKmiPbxzLOMAs3F9QK6ZYqEwG0Qv0NUwkzlkrLVrA5oAssArVCro2v0wP7OkWte4FrglrNlE29BI1+opiI3NtvH9r2X9Dc8Ha+I='}]}]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def apply_line_patch(data: bytes, spec: dict) -> bytes:
    lines = data.decode("utf-8").splitlines(keepends=True)
    for op in reversed(spec["ops"]):
        old_segment = "".join(lines[op["i1"]:op["i2"]]).encode("utf-8")
        if sha(old_segment) != op["old_sha256"]:
            raise RuntimeError(f"Neočekávaný obsah při aktualizaci {spec['path']}.")
        replacement = zlib.decompress(base64.b64decode(op["data"])).decode("utf-8").splitlines(keepends=True)
        lines[op["i1"]:op["i2"]] = replacement
    return "".join(lines).encode("utf-8")

def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    app = root / "app.py"
    if not app.exists():
        raise RuntimeError("Ve zvolené složce nebyl nalezen app.py.")
    version_file = root / "VERSION.txt"
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == TO_VERSION:
        return 0
    if current and current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current}.")

    targets = [root / spec["path"] for spec in PATCHES] + [version_file]
    backup_root = root / ".update_backup" / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_patch_0134")
    backups = []
    try:
        for target in targets:
            backup = None
            if target.exists():
                backup = backup_root / target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))

        for spec in PATCHES:
            target = root / spec["path"]
            old = target.read_bytes()
            if sha(old) == spec["new_sha256"]:
                continue
            if sha(old) != spec["old_sha256"]:
                raise RuntimeError(f"Soubor {spec['path']} neodpovídá v{FROM_VERSION}; aktualizace jej z bezpečnostních důvodů nepřepíše.")
            new = apply_line_patch(old, spec)
            if sha(new) != spec["new_sha256"]:
                raise RuntimeError(f"Kontrola výsledku selhala: {spec['path']}")
            temp = target.with_name(target.name + ".patch_tmp")
            temp.write_bytes(new)
            os.replace(temp, target)

        tempv = version_file.with_name(version_file.name + ".patch_tmp")
        tempv.write_text(TO_VERSION + "\n", encoding="utf-8")
        os.replace(tempv, version_file)
        return 0
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup, target)
                elif backup is None and target.exists():
                    target.unlink()
            except Exception:
                pass
        raise

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
