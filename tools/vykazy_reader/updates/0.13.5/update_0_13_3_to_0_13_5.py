from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path

FROM_VERSION = "0.13.3"
TO_VERSION = "0.13.5"
EXPECTED_RAW_SHA256 = "86732c2f8ece589530aac6b6a3c6e7e70bad782d8648b61573704b973634d058"
EXPECTED_LF_SHA256 = "35e2579985fc386a2269aecea53d38c153b985221acf94e4e2b83477ab78a956"
NEW_SHA256 = "aec821c0731c502713e023bd161d887002bcbe3371cb034694105f395090755b"
OPS = [{'i1': 27, 'i2': 28, 'old_sha256': '70eb63602bd52c80483ba250d43a9ff491036f13e6d2e5f22fa47a97ae6616a6', 'data': 'eNpzDAiID3MNCvb091OwVVAy0DM01jNV4gIASlQFVw=='},
 {'i1': 30,
  'i2': 30,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNoLCPL3cnUOiQ8OcQwJDXYNVrBV0FAKyq8qKEpMzi87vDAvX0lHQck7VSE7P6+kKD8nFcSNgnIQClwrCvKLSqB8TS7XiAD/oJD4gCB/N08fqKHeED15h9cqaGTn5xbkpJYA2Zog3WGH92YnVikUFOUr5CdlpabkHV5Yll0KNAcA+no4cQ=='},
 {'i1': 96,
  'i2': 96,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpVkE1Lw0AQhu/+ipcI0gqm9SoU8aSCp4LnZpJMmqX7EXdnLaH0vztJteAelpnZnWceBgBu8WrkLdfY0hGf24+E4CE9w4Vv4/eoKkfGVxXqSL7p4WhEzWio6bnVSI7MHpo0h1TeYCa+XJ4f6pxkYnxljiMOzEOa0XloSXQCedNxEnSRU1/i3bksVFulB+eMzDq/yJx0Whfi3E+NZLIYSFRooNEGahMoMlq2puaodDvCcifIKk1+z+1FLrLKJNnlaLGB3nPVdCgiHcu9kT6rNccmeGEvpZoUMH76CfItitW0jtVf7Wlun07igXSuGm5Q3BUz8vnayjbxlF+///foipMG59MVct5JjhI2J+NlMS1LjOPSh+NiWU5hEnLDYol7PK7X6+W5uPkBHZqXrQ=='},
 {'i1': 97,
  'i2': 99,
  'old_sha256': '7af61cb3f90dac726d0e073d5f944493f370f3c1dca8adaa759d6aee11845653',
  'data': 'eNpTUICAotTC0tTikvjSohwdLqiYQkZqYkpqUbFtNVwEBJRCi1OLdB3TU/NKlKwU0pRCQoNC/HXDKrMTqyr1qx0DAuLDXIOCPf39apV0UDU6JyZnpOo65+eVFOXnAPUq5eXrJoPE0BUGFCWm5ybiUFGrwwUA+ZcuSA=='},
 {'i1': 1463,
  'i2': 1464,
  'old_sha256': '9353fba800924bfcc7ea80e25485cc005cc9147432e8053c936d7015e075d78e',
  'data': 'eNpTUMAEpQUpiSWpKfGJJQohrhEhCn7+QBzq46PDhUWxQnFJYklpMapKBRdXN8dQnxAF9aD8qoKixOT8ssML8/LVuQBnjBw8'},
 {'i1': 1559,
  'i2': 1559,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpljs0KgkAAhO8+xbAX9RJ0DTpsaV1WDVkhiBCTNTZiV9Y1pOhhepZerCT6kQbm+H0zwDeik42Vap/XRh9EaRtMcTGb8RaVNjCQCqVWI9GJsrXCI6uULiMKW+yOIpeq0t4b9Il/dX7MkBVIYwvbNgRK2171tzYZEH0Ga5TxMAWnMxbic5AGAeYJy6IYLz14uOaIk2czxhCEC5oxDjfV59oUpT7db0q7xHce95RMIg=='},
 {'i1': 1604,
  'i2': 1606,
  'old_sha256': 'c19ebd0b0e4ec897a0a323678cd84c97026ac7f996a3281a6ae8803bdbed6632',
  'data': 'eNpTUEAAJU+/YNegEAVPvxB/hYKi/KzU5JJijbzE3FQdhbz8otzEnMyq1JR4iEByUWpiCZCXWKKjUFqQAmcXlySWlBZrKoQ5+oS6BmvY60ChppIOF5JdCkjmgshyKKEUlF9VUJSYnF92eGFevpKmDhcAN3gwiQ=='},
 {'i1': 1635,
  'i2': 1635,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqdkk1OwzAQhfc5xcgrWwqR2FYKFYIghPhT05YFQpFJpqoh2JHttNDb9CCwqbgXTpo2hHYBzCq2Z+Z9byYeuMhwAoVWT5jaxFhuS0MN5hN/eymyHghpGRwcgbG650ETc2GnUOUGqZLSpVIG3IA7tDlVaDWHsLoO8BXT0iIlcXQZnQxhrQdng5urjZyBu/NoEIHIwj7xgTpl2pIwn7FggjadKomUbWVmPC/RiTg+6uTuybozeQClgRAGYlJjYG7Qnbd1Gm2pZVPucpoPCbeDmwtHmMTD4+EojuKmcqAWheapmq2WUhHP2wzQoE1+M0S/sdyrSOuJXjsj7biagYQglX7huVhgYgqeomtXv7SOHWyTLJXdR/xjB1w4/nFlL9JaaUqusci5lav3qs8M+HOKAWF/Xq7jqAD2bffw/4vtauw3MH571FyuljU6lJ8fMIOMW/64Wi4ESMRXYWz51HFVxXfUHRkyuj09HkYtdBxtftOw70NZOAXMEm7DfsfPTqNmYT4kUs0TYRRlPvzwzLplzPsC3OwTdw=='},
 {'i1': 1910,
  'i2': 1911,
  'old_sha256': '5386b57907d7f8f6dce818d4c76f5c6ab1ff8d1d0064c2026d38882651688879',
  'data': 'eNpTUECAYFcfV+cQhQK9zBSdAr28xNxUIFVcklhSWgxkJBelJpakpsQnlgA5pQUpMA4XAGUfFJY='},
 {'i1': 6232,
  'i2': 6233,
  'old_sha256': 'b33a7dc302c0aa01cd0ed5fc66d607c30eb8e42b415740682045b1f1c3d4b363',
  'data': 'eNoljUEOgzAMBO99heUTSBE/yC/6gTRZCpQkKDbk+3XLXnZXGmmI7gj2eTpa3RBVyJPqZ3o24FrRh2NuIcNRrPuZi/iBi312LBr0FBspKP6NWBOSrYZLeHQkS+2eF4S0lrchP5M5smGeX612AY+PL6VCLHQ='},
 {'i1': 6234,
  'i2': 6236,
  'old_sha256': 'cd05f57c6258405d669a89a3c09ef94cd16f87353945ba5ac160ee3732faed9f',
  'data': 'eNpVjj0KAjEQhXtPEaZSSOHfggewFkGwD5lXxU0giRH2NnsAsbC2Ct7LCQrqdI/3841S35uSNz1I066OA4oyzoparjtNF5pp8VM2+ZwkccimkF7MN5osfEZ8+2wymr2VWK9KfbiI9LxJcvUZmag/IMMGBktlH9IJ7OtVMVy9cyh1FCXVH35EafNHxEE+64SOtvkCit85rA=='},
 {'i1': 6440,
  'i2': 6441,
  'old_sha256': '7ea25fe3b77563f60bda42f206734650425bcdaa483fba2e366d21ff6a2c770a',
  'data': 'eNpdjEEKwkAMRfc9RchKYU7jVkoIkyAD7aRM0orexrN4MetAF/pXH95/H+A37YqVZ8UxfasHx+o4gjXAiz2Xxtm296sadi6N76XeSDj0mGEa/j6BpPgy8aPvosx62t2JPUg0m6gQx2Gf+3HTrXixStnWurM0fABKwzOm'},
 {'i1': 6669,
  'i2': 6669,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiK4XikiIFWwUlJS4AUX0Osw=='},
 {'i1': 6682,
  'i2': 6682,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUICA4tScNL3UioL8opL4gqL8tMyc1PiyxCIFW4WSbL3gkqLMvPSwxCKNssSc0lRb14gA/6CQ+IAgfzdPH9fgaINYTS4Ab+AX3w=='},
 {'i1': 6970,
  'i2': 6970,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqNUDsLwjAQ3v0VIVMLoajgImSSCkKlog5uJW2uWowmJFeN/974wPfgTQff846Q2yBuk0yUoCIHqk7AG22xWFvdGkYQPHKa+grUkDLi8KSA02mLIJPlVUXjxIhqG7lGBkRBjYFnhPQ86nUZGcRx5x5EXv2N1XWjoKj0rtSEX1uMLnupffRQfKrurRwKDGEWhNR7daK3ngdhG1GGfr9yAsjebA9CteB4uprl82Uxm+fjSZYuGDk2Eje8332y/zjg6wVx5wyLGW5/'},
 {'i1': 6987,
  'i2': 6988,
  'old_sha256': '48fd42f08073efe299aee53188e08e6c6d505016205a881a877ee08d92f66bbc',
  'data': 'eNqNUklOwzAU3XMKy6tUiqIWwQbVlaC0C1SUqilsEIoc201NEjtyfjrsOAQbDsEpEBfhJDhN6QBl8Or722/4A0L1oQykVqGR8RQQQZB4fUMz4azzUShgPRTEpRDrze6PhaBLcYUYNx/duAx1g8WMjuWP0kjQ9xHRaZoqceKgAyZI1wQJ7KKd8RZyWzTbdLxKw4kMaidTZp/MQiBUQHABdnOGKZ50Kgq9LENyfbuqx6+eUJU4huX1JxQx2GtZCe09i08SWvQAKZREuqKn7DsBIFd9S4yxoWlqi98cnfBTKdBbpCmzRvSqO9MrZAX7OpbJOwfJyWdAoFRzXrVkDsrqTw+Y8tLFTkPFkdNXvTcNgej69CfqBh5aSw5y02t5O82+7xyZ16v4DH0nFHdzpfDYciFQwu4tut1pOhQrZnKpYhKw0RigIc6MfbMmW5vu+L0oArQ4ufARi8fb8+gJofDlANGHVz7EeMqp4PatQ50LtZLhmZWaD4vdvcBsfLZb11w=='},
 {'i1': 7236, 'i2': 7236, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4sSy1JT4kvz4lCQFWwW3xJziVC4AZ3oH7Q=='},
 {'i1': 7285,
  'i2': 7285,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUECA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVuIbEpiSWJSYnGqHqq0BoybmaLJBQBiRhzl'},
 {'i1': 7288, 'i2': 7288, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUECA4sSy1JT4kvz4lCQFW4WQotJULgBufwgi'},
 {'i1': 7304, 'i2': 7304, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUEAFxak5aXrJpUVFqXkl8QVF+VmpySXxxSWJJaXFCrYKSkpcADN1DgA='},
 {'i1': 7382,
  'i2': 7382,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqlV0tvGzcQvvtXsHvJLuIK6aFoIdQtlERBFbuSIcsBmsRYULuz1la7pExSkqUghx578N1IT/kB+QnpRfb/6pD74q4kpw9dlo/5hvP4ZkgRkv28g4N8RK7mNInVihwRCUnU8imjyUrG0s83fDlPUypWrldC4ohIuoDQV9wPx4SyMMMGcyGAKX8m+G8QKD8O2yVG/5RY1Rf0zyBDquiYSmhJqOBSUTWX7h7Vh4Xlbxw5v7wEqdCgDOJceLuPaWrJxNH1B1Tt1uQLiATIiU8DFXPmT4CGINz6uXAdwEyRrvmgFKFSr+2JgZ/wS9c5HQ5edp+NyNmoMzo/I93hcDBsE4c8JgJmwkW4Vx1icDRSePL3Tw5JQtNxSMnVUe5OO1csJ3y5P69XXs6GECKyX0yr8sjXP5IwDtQbqcQh4WMdxYvKH4giXIgXgCEtx36UcC58wZfSjwRPfcnnIoA8sfmk8mlMNa+mwHRe3FqonGc///p0c+McZqOeHrw+HvRHw8HJ4FVnpOen97e9+9vO8142G/aGxbjffdk7G23+qMZd57Cuv9/dfDg96Rcy5zjuZsPBq7sP97fd/qCYdoflpN856b7OZ8PB6+ebm5Ni2DtpHqEN71iLViXq+DOAUCK5FjEsXQxZmzwFmg750oR+zHlSZ0/JYMZFiglbgz+FlUa2sq06I7FyKVu5Jr4kZgU84oKUa1UCvG2mClBzwchIzKGpWJ8JCaS6wNRqhhw4Is4YrXe21aA44yqDXGMJ+YymQNAK5ydH21Df2MY/ZIplTsBZFIfAAiA/kCet7779d5og2ecWVxMQjul8ev8K+2csjUt9zuCfhy1ff0ETCRURsvSbisHMvhEmP0LHpSqwuMkVr+pUQQJUFPCUXru6NwBzSzSSySxYB3kWEWUwgXCeQHW4NGSx6tXcAa1pjAHQ8TAl7lR2ypbWWVkUCrqM2eX/UZir8OuKjZx2U3KBXbveL96JltnfE79i12QxH+sUopyLPMQSPjv/ZfP7/W0+7Awd7329nLHWjhiWkKBJ3uZwxS7uMiWcKcETP4zRAqEZqY1+UvmhrTQW4OmZU3UWYUqCqcYEPJ1RAX4RjyJZ7hbpbOKUKbX8xjibwcXhg9Aid19G1nvNLpcfY6Lm6bap31TH5Y7mHcIVeR/TH6HkMlYT1xkcO57uFjs3e/0XA8fz9liWd0CLavkF5+zmZaMH5sL+Vjo0Lbf9Kvm2N8RfKoSadXZt/cfQW5Fu+FL05H0BtxrELIz8JRUMaWFqr9T7kDdfoTfxJd5TEGadU99mmIhckf2sKR5hqNs5BjLN3AHHcNBqjnjiLldxuWYhYHfF+5ivZ4IGfLH5yLhz0GjB7+rXtFbvtBtds3GVmzaLQlW7bQhkpuZq7F7bkLNs1+q2PWrI284hwJ42JLees+0quJXoe+v99/BbUae2fHi3t5+C5pVSvwJzWhlSYB+JuA/XsVTSbVRWlodyKQUp6SWM+XVLm6SBjcdgZ654SlUcTDcfC4pQok3ffF6vmu+uTrZOyXiFUiFHwN0NMNp6y94ypyYbOac84fd/wZTgRbHYfJ7SNQSTNnlX/E14pLP46OL9NvIlhIyvGb27YXd/Ev1VwLgNNWzZiT0mYo64zaeS8LUjDX92AzNxjRR8HW4+JSsbaRFpJ/x8xtdcoL1awenzFzbW5pYBb8P7dCEwWGzzWT8nF4ROg5rhTQ6imkZydANl6siQ6+BvWflmfg=='},
 {'i1': 7749,
  'i2': 7749,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqVV9tu2zYYvu9TEOyNtLlC0rVYG0AD0tTZWrRNkbgHwDUIyqJs1hKpkpRsJ8gj7AF22Ytd9hG2m6zvtf+XfJBlO211I5H8z4ePvwghJBYJYRk3EzYsjBHKsdzoj2LomJjl2jgRe1akiU/u/UZeaSWO7pDFIxOitCN4GrR5Zbymw8cIVxi12nJmvnleCYm54xG3IrBiLck67grr7dHSIbRbmanLm89KU39bapupFkjCFuc2IzMiMcKOGR86qRUbCx4L461ViNlQ5I50qxdQEG5xb4dnLNUjj74+P3vePemR7vvXZ+c9ctE77r25IN3z87PzI0LJzxCl3HggwffvVDKq3NRpYNqAcjZL7eyWfLzTZhJpPSHStg7xyYS1fCQiPQvsWE+FMdp4GxT4LMJSuZXSzvb5yXge3XwhEyXHulSc6FyofD5LA3KRF/br306QS6XLgjx7BS6+OHt73Asi7oIP6oNCL60z3vsXF+/Zs5cYB1YFgGhDKPW31eUcsxeiz5uH/m0FJpIEci1LAXlefbMk1dowo6eWJUZnzOrCDMWiuBaLtdiR0UUu4iMSy6HruyJPRR9s76ADg069W611hIU1GICuq+sVewIegSoi1dqCzXxAwoAgEKnIsEDdPAdzoS61GwtDSc0ffHLz3enEZ6iVk6oQGwexsHKkeFWSIfSoyXgqLwWzOUdvK50zKGqmeCaWagyfVuvNsBZKun0yPhUclLs5q4hAjEejjO71SqpEpiklIrWC0Imlvt+OBsJJw/jvdHci5mCit7YRNryGGL9DNs/Q3rZyJzIQskg5AhD0Hi9S5wFDh1zRhjx61DQSEAgyBHsHwQF8o2xY4Ot6W0W/osVCgVLkzmvs+dAZ9eYi6QsMaIRmWZC3NTVEWXv07c0/E35JAPKq4ozVzedyUlCw7y3hk6EkSnyEeie5TvXXfydzYkmm4Mu68uZLRiakBp0iAJZGA+5sudWe5Qm2G8M3G+osh4pVbjdyLyuP9t6c985YOQdzQdejg7WKnLsxBkqmIpYcADTgdmJ5KbjFPZSwCV5Qi6kI9/reapEqu2LmhLKQxZAGCK0tKglZBNWoLkzoFTp2Te41xPJdXEiOVW/DvkcXKEroTzWpP1gT++0Eo8s/dm9OIwjREvW9zfxM8ZKbRgGvoKd1FFTRwltwT7za9DwHmI+9Pj27VPy/P4W6+YJuvVyVTbV6DoW8GQxIctVcAIO2HieWTVbytAAogfaEHgtTnkUxJ7OjVrPibTHrb/TfwPf9bWxo2Fi31QZLp9l/y0XVrINBo9Pwqe95hmgF8XnNnRNGncLKo1anMgZHk9EJdI4J6eHp/ce//NoaO9xYIvBeyFiA+XMsStwCvmHN9fTx0273Id2OFNRKipGa2v7hYAf8wXGQAAaC9FN4edgEIT2BaEVGgnwLUQsPAYcincZhzxRipfO0elo610JrZxuu76YDTSOFuA7Ex8tvrxTGySFPQzqEJdxd257hrJSyxX0IqYIE1Dexl0mFH+H9HTltxmQlYZvsR2Lj7+eOqhkL+J9UH16kndNZiLm7hetbIXE63xH1lTeQ6EAVWYRhx8JHMfQguHv37lYLQiaLTLFYZjVo2T49poNgKuMKKR88+g6GJw2GwwffwXDSZDhoM8CALKBRc65ENVIf398GjsJprChIeAATNWKSDdYa2uR2LGD6L6WYVvfZ70bGL2Qt/ZTD6NCmz+HyY3BfFzkUsevpd0tbv0X4h5CjMUa75VQU4CXjIRbv+Jv4xq/SDo76f4OV3OBY4SV7AJcUeBULdUSuUPU1/cH/jJ3D/f5BIKlvJjARZoFcx/zrXzLVpJy7UsNnPa1fgZbr9ghw539vukVE'},
 {'i1': 7759,
  'i2': 7759,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUECAotSS0qI8Lhg3M02hODUnTS+1oiC/qCS+oCg/LTMnNb4ssUgvPbVEQ1PB1lZBKezw3uzEKgWgpEJ+UlZqSt7hhWXZpUpWXEjmQoyJh5qTX5SSWhRfkVNcoaHJBQBbNCfD'},
 {'i1': 7941,
  'i2': 7941,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUEAFGkrBJYllConZyalKOgrFqTlpesmlRUWpeSXxBUX5WanJJfHFJYklpcUK+UUKSo8apihp6nABAHLVFPk='},
 {'i1': 8283,
  'i2': 8283,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUECA4tScNL343MSi7Pjk0qKi1LyS+IKi/KzU5JL41IqC/KKS1BQNTS4AbaUQQA=='},
 {'i1': 8389,
  'i2': 8389,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqljs0NwjAMRu9MEeXUSqgDILEEC0Ru4kJQiCvbrQQnhmABZmETJqGlF/4OIN7Ren76jJmIjdmAgCoXgqmZGwteI2UnCtqJ64FtuZiZB4aXUa18x4xZXcu0Ra8uhmdv5C6+FStBLT42JscQG7uiQ8vgqb+cM9nym7SnXU2Vp9zEdcdYjGdcWkYIlNP+JYJJ8KfF9no8/TUkRIE6YRgiN04ceOI='},
 {'i1': 8390,
  'i2': 8390,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNqVksFKw0AQhu95iiGnBEoeQOhBpBcPKqbeCmGaTNpouht2J7FaCn0NUXwUT/ZF+iTutrFpGi06BLJs/plv/p84YCqhFKJCyXuKOdKMXoonqKYUOJpytMeUEWC+1dSkH/mQF1ZCkIyWEUQl0oZyX5KljQ6W4q4VGJ/tYNAf9eMMWdSfJMrVMGE2PMPQXWD5WUCbm6vLwcXwygcng/vwkF4ksXqqf19y0yQcYyaAk185N37xVGv3sLvTjsWN/62h27DgVezgJe6IWMF+BATPM8+X4V5QCBsVu+LnXS5Wb0FboOmeUwFw2D7MukBanvXdjojrXFCYzkP9FQ+klJSeQ3K7UEN1gSCCpng+iXLJZS5XH9kHIzESCzM1KVRFmgd9u32/wqgFfbfgv5hfvcXsbGdQPvOF/l08Xo='},
 {'i1': 8486,
  'i2': 8486,
  'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVuIbEpiSWJSYnGqHqq0BoybmaKpkJmmgOAqpOYUpyooKXEBAAnBI8Q='},
 {'i1': 8539, 'i2': 8539, 'old_sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'data': 'eNpTUICA4tScNL3k0qKi1LyS+IKi/KzU5JL44pLEktJiBVsFJSUuAAXtDQA='}]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def choose_root() -> Path:
    candidates = [Path(sys.argv[1])] if len(sys.argv) > 1 else []
    candidates.append(Path.cwd())
    for candidate in candidates:
        try:
            root = candidate.resolve()
            if (root / "app.py").exists() and (root / "VERSION.txt").exists():
                return root
        except Exception:
            pass
    import tkinter as tk
    from tkinter import filedialog
    r = tk.Tk(); r.withdraw()
    folder = filedialog.askdirectory(
        title="Vyberte složku TURTO – Výkazy kladecích plánů (obsahuje app.py)"
    )
    r.destroy()
    if not folder:
        raise SystemExit(2)
    root = Path(folder).resolve()
    if not (root / "app.py").exists():
        raise RuntimeError("Ve vybrané složce nebyl nalezen app.py.")
    return root


def notify(title: str, text: str, error: bool = False) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, text, parent=r)
        r.destroy()
    except Exception:
        print(text, file=sys.stderr if error else sys.stdout)


def restart(root: Path) -> None:
    vbs = root / "SPUSTIT_BEZ_OKNA.vbs"
    bat = root / "SPUSTIT.bat"
    if os.name == "nt" and vbs.exists():
        subprocess.Popen(["wscript.exe", str(vbs)], cwd=str(root))
    elif os.name == "nt" and bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(root),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen([sys.executable, str(root / "app.py")], cwd=str(root))


def apply_patch(old: bytes) -> bytes:
    # The uploaded live 0.13.3 may use CRLF. Normalize only line endings after
    # verifying that the normalized content is exactly the diagnosed source.
    lf = old.replace(b"\r\n", b"\n")
    if sha(old) != EXPECTED_RAW_SHA256 and sha(lf) != EXPECTED_LF_SHA256:
        raise RuntimeError(
            "app.py není totožný s diagnostikovanou v0.13.3; aktualizace nic nepřepsala. "
            f"SHA-256: {sha(old)}"
        )
    lines = lf.decode("utf-8").splitlines(keepends=True)
    for op in reversed(OPS):
        segment = "".join(lines[op["i1"]:op["i2"]]).encode("utf-8")
        if sha(segment) != op["old_sha256"]:
            raise RuntimeError("Vnitřní kontrola aktualizačního úseku app.py selhala.")
        replacement = zlib.decompress(base64.b64decode(op["data"])).decode("utf-8").splitlines(keepends=True)
        lines[op["i1"]:op["i2"]] = replacement
    result = "".join(lines).encode("utf-8")
    if sha(result) != NEW_SHA256:
        raise RuntimeError("Kontrola výsledného app.py selhala.")
    compile(result, "app.py", "exec")
    return result


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".update_tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def main() -> int:
    standalone = len(sys.argv) <= 1
    root = choose_root()
    app = root / "app.py"
    version_file = root / "VERSION.txt"
    current = version_file.read_text(encoding="utf-8-sig", errors="replace").strip() if version_file.exists() else ""
    if current == TO_VERSION:
        if standalone:
            notify("TURTO – Aktualizace", "Verze v0.13.5 už je nainstalovaná.")
        return 0
    if current != FROM_VERSION:
        raise RuntimeError(f"Tento krok očekává v{FROM_VERSION}, nalezena v{current or '?'}.")

    result = apply_patch(app.read_bytes())
    backup_root = root / ".update_backup" / (
        datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_0133_to_0135_exact"
    )
    backups = []
    try:
        for target in (app, version_file):
            backup = None
            if target.exists():
                backup = backup_root / target.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            backups.append((target, backup))
        atomic_write(app, result)
        atomic_write(version_file, b"0.13.5\n")
        if sha(app.read_bytes()) != NEW_SHA256:
            raise RuntimeError("Kontrola zapsaného app.py selhala.")
    except Exception:
        for target, backup in reversed(backups):
            try:
                if backup is not None and backup.exists():
                    shutil.copy2(backup, target)
            except Exception:
                pass
        raise

    if standalone:
        notify(
            "TURTO – Aktualizace",
            "Aktualizace na v0.13.5 proběhla úspěšně.\n\n"
            "Databáze akcí ani archiv PDF nebyly měněny. Program se nyní znovu spustí.",
        )
        restart(root)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        notify("TURTO – Chyba aktualizace", f"Aktualizace se nepodařila:\n\n{exc}", error=True)
        raise SystemExit(1)
