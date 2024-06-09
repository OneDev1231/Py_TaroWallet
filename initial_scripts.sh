
# initialte terraform



# initiate DJANGO

pip install install django~=4.0

django-admin startproject tarowallet

cd tarowallet

python3 manage.py runserver

python3 manage.py startapp walletapp

python3 manage.py createsuperuser

python3 manage.py makemigrations

python3 manage.py migrate

in instance


sudo yum install wget -y

wget https://bitcoin.org/bin/bitcoin-core-22.0/bitcoin-22.0-x86_64-linux-gnu.tar.gz

tar -xvf bitcoin-22.0-x86_64-linux-gnu.tar.gz

rm -rf bitcoin-22.0-x86_64-linux-gnu.tar.gz

echo 'alias bitcoind="/home/ec2-user/bitcoin-22.0/bin/bitcoind"' >> ~/.bashrc
echo 'alias bitcoin-cli="/home/ec2-user/bitcoin-22.0/bin/bitcoin-cli"' >> ~/.bashrc
alias bitcoind="/home/ec2-user/bitcoin-22.0/bin/bitcoind"
alias bitcoin-cli="/home/ec2-user/bitcoin-22.0/bin/bitcoin-cli"

mkdir .bitcoin

nano  .bitcoin/bitcoin.conf

bitcoind -testnet 

#sudo yum install golang -y

wget https://go.dev/dl/go1.21.3.linux-amd64.tar.gz
tar -C ~/ -xzf go1.21.3.linux-amd64.tar.gz
echo 'export PATH="/home/ec2-user/go/bin:${PATH}"' >> ~/.bashrc
echo 'export GOPATH=/home/ec2-user/go' >> ~/.bashrc

sudo yum install git -y

sudo yum install make -y 

git clone https://github.com/lightningnetwork/lnd

git clone https://github.com/lightningnetwork/lnd.git
cd lnd 
make install tags="signrpc walletrpc chainrpc invoicesrpc"
cd ..

git clone --recurse-submodules https://github.com/lightninglabs/taproot-assets.git
cd taproot-assets
make install
cd ..



bitcoin.conf .bitcoin/bitcoin.conf

bitcoind -testnet 


lncli --macaroonpath=~/.lnd/data/chain/bitcoin/testnet/admin.macaroon stop | echo "error stopping lnd" ;

sleep 3 ;

tarocli stop | echo "error stopping tarod" ;

python manage.py flush --noinput ;

sleep 3 ;

rm -rf ~/.lnd ;
rm -rf ~/.taro ;

lnd --bitcoin.active --bitcoin.testnet --debuglevel=debug --bitcoin.node=bitcoind  --feeurl=https://nodes.lightning.computer/fees/v1/btc-fee-estimates.json

lnd --bitcoin.active --bitcoin.mainnet --debuglevel=debug --bitcoin.node=neutrino --neutrino.addpeer=faucet.lightning.community --neutrino.addpeer=btcd-testnet.lightning.computer --neutrino.addpeer=testnet3-btcd.zaphq.io --neutrino.addpeer=btcd0.lightning.computer:18333 --neutrino.addpeer=lnd.bitrefill.com:18333 --neutrino.addpeer=testnet1-btcd.zaphq.io --neutrino.addpeer=testnet2-btcd.zaphq.io --neutrino.addpeer=neutrino.addpeer=testnet4-btcd.zaphq.io --rpclisten=0.0.0.0:10009  --feeurl=https://nodes.lightning.computer/fees/v1/btc-fee-estimates.json
lnd --bitcoin.active --bitcoin.mainnet --debuglevel=debug --bitcoin.node=bitcoind  --feeurl=https://nodes.lightning.computer/fees/v1/btc-fee-estimates.json

sleep 10 ;

expect reset_lnd.sh ;

sleep 10 ;

tapd --network=testnet --debuglevel=debug --lnd.host=localhost:10009 --lnd.macaroonpath=/home/ec2-user/.lnd/data/chain/bitcoin/testnet/admin.macaroon --lnd.tlspath=/home/ec2-user/.lnd/tls.cert --rpclisten=0.0.0.0:10029 --restlisten=0.0.0.0:8089 --allow-public-uni-proof-courier --allow-public-stats --universe.public-access --batch-minting-interval="1s" 
tapd --network=mainnet --debuglevel=debug --lnd.host=localhost:10009 --lnd.macaroonpath=/home/ec2-user/.lnd/data/chain/bitcoin/testnet/admin.macaroon --lnd.tlspath=/home/ec2-user/.lnd/tls.cert --rpclisten=0.0.0.0:10029 --restlisten=0.0.0.0:8089 --allow-public-uni-proof-courier --allow-public-stats --universe.public-access --batch-minting-interval="1s" --proofcourieraddr=hashmail://mailbox.terminal.lightning.today:443

lncli -n=mainnet openchannel --node_key=035e4ff418fc8b5554c5d9eea66396c227bd429a3251c8cbc711002ba215bfc226 --connect=170.75.163.209:9735 --local_amt=200000 --sat_per_vbyte=90 --min_confs=1

git clone https://github.com/rgb-org/rgb-node.git

curl https://sh.rustup.rs -sSf | sh -s -- -y 

sudo yum -y update 

sudo amazon-linux-extras install epel -y


sudo yum -y groupinstall "Development Tools"
sudo yum -y install gcc gcc-c++

sudo yum install -y build-essential pkg-config libzmq3-dev libssl-dev libpq-dev libsqlite3-dev cmake

cd rgb-node
cargo install --path . --all-features --locked
cd cli
cargo install --path . --all-features --locked

echo 'alias rgbd="$HOME/.cargo/bin/rgbd"' >> ~/.bashrc
echo 'alias rgb-cli="$HOME/.cargo/bin/rgb-cli"' >> ~/.bashrc
echo 'alias bcli="bitcoin-cli"' >> ~/.bashrc

git clone https://github.com/Storm-WG/storm-stored

stored

[2023-03-28T12:48:27Z DEBUG rgbd] CTL socket ./data0/ctl
[2023-03-28T12:48:27Z DEBUG rgbd] RPC socket 0.0.0.0:63963
[2023-03-28T12:48:27Z DEBUG rgbd] STORE socket 0.0.0.0:60960

--lnd.macaroonpath=/home/ec2-user/.lnd/data/chain/bitcoin/testnet/admin.macaroon --lnd.tlspath=/home/ec2-user/.lnd/tls.cert --datadir=/home/ec2-user/.taro


wget https://repo.anaconda.com/archive/Anaconda3-2021.05-Linux-x86_64.sh

