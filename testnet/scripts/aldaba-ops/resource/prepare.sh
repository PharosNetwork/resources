echo "INFO: prepare aldaba ops"

pip3 show pipenv
if [ $? -ne 0 ];then
    echo "INFO: cloning aldaba-ops.git -b user/youxing/dev"
    pip3 install --user pipenv==11.10.4 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
fi

if [ ! -f "Pipfile" ];then
    echo "INFO: creating pipenv --python 3.6"
    ~/.local/bin/pipenv --python 3.6
fi

if [ ! -d "aldaba-op" ];then
    echo "INFO: cloning aldaba-ops.git -b user/youxing/dev"
    git clone -b user/youxing/dev git@code.alipay.com:zhuyusong.zys/aldaba-ops.git
fi

cd aldaba-ops
~/.local/bin/pipenv run pip install -e . -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
cd ..

~/.local/bin/pipenv run aldaba-ops --version

