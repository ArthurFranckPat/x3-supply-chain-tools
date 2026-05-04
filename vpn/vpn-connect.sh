     #!/bin/bash
     if [ -z "$1" ]; then
         gp-saml-gui --no-verify --allow-insecure-crypto -g gp.aereco.com 2>&1 | grep -o 'https://[^ ]*'
         echo ""
         echo "Lance ensuite: ~/vpn-connect.sh TON_COOKIE"
         exit 1
     fi
     echo "$1" | sudo openconnect --protocol=gp --useragent='PAN GlobalProtect' --allow-insecure-crypto --servercert 'pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q='
     --user='ALDES\bledoua' --os=linux-64 --usergroup=gateway:prelogin-cookie --passwd-on-stdin gp.aereco.com
     EOF
     chmod +x ~/vpn-connect.sh
     echo "alias vpn='~/vpn-connect.sh'" >> ~/.bashrc
     
