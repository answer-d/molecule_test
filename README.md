# Moleculeに入門してみたよ

## Moleculeってなに

[Molecule](https://molecule.readthedocs.io/en/stable/)はAnsibleロールをテストするためのツール  
分子って意味らしい  

pythonモジュールで実装されているので、`pip install molecule`で使える  
使い方もとってもかんたん、`molecule test`  
これで、  

- プレイブックが正しい構文になっているよね、コードがある規則に基づいて記述されているよね、を確認する(lint)
- dockerコンテナを立てて、作成したプレイブックを流す
- ↑のコンテナにもう一度同じプレイブックを流して冪等性を確認
- 事前に記述したテストを実行して、狙い通りの動きをしているかチェック

みたいなことをやってくれる  
つまりAnsibleロールのテスト自動化ができるツール  

もちろんテストの内容やtestコマンド実行時の動作はカスタマイズできる  

## なにがうれしいのよ

Ansibleロールは一回書いて終わりじゃなくて、何度も修正していくはず  
そんな中で、何度もロールの動作が正しいことを手で確認するのは大変であることは明らか  
こんなときに、Moleculeのようなテスト自動化が役に立つ  

テストが自動化されていれば以下のようなうまみが得られる  

- 人間が毎回毎回手でロールの正しさを保証する必要がなくなる
- 機械がテストをしてくれるので定義された試験項目をもれなく実施できる
  - 人間がやるとサボりが発生するのでデグレードの心配をしなければならない
  - 特にlintとか構文チェックとかって人間は毎回やらない
    - だいたい「まぁあってるやろー」→「あっ…」ってなるのがデフォなので機械的に救うのは理にかなっている

更に、ロールをGitみたいなバージョン管理ツールに入れておいて、コードに修正が入ったとき自動でテストが流れるようなパイプラインを作っておけば、コード修正時にテストを自動化するといったこともできて素敵になる  

要するに、IaCをするならテストは自動化されているべきで、それをAnsibleロールにおいて実現してくれるのがMoleculeだよ、って話  

## Moleculeを使ってロールの開発をやってみる

ハイパー実際にMoleculeしてみようタイム  

### 作業環境

|品目|バージョン|
|:--|:--|
|OS|macOS Catalina 10.15.2|
|シェル|fish, version 3.0.2|
|Python|3.8.0|
|Ansible|2.9.2|
|Molecule|2.22|
|Docker Desktop|community 2.1.0.5 (40693)|
|Docker Engine|19.03.5|

### インストール

- Docker Desktopを入れておく
- 適当な作業ディレクトリにcdしておく
- pythonの仮想環境を作ってアクティベート
  - 私はfishシェルを使っているので、bashやzshの方は`source`の部分を適当に読み替えて下さい

```console
$ python -m venv .venv
$ source .venv/bin/activate.fish
```

- Moleculeをインストールする

```console
$ pip install molecule
```

- ロール置き場を作って移動

```console
$ mkdir roles
$ cd roles
```

### `molecule init`でロールの雛形を作成する

- 今回は[Anisbleもくもく会](https://ansible-users.connpass.com/)の教材になっている、[httpdを構築するロール](https://github.com/ansible/workshops/blob/master/exercises/ansible_rhel/1.7-role/README.ja.md)を題材にする
- ので、ロール名は`apache_vhost`として、Moleculeに用意されているロール雛形生成コマンドを実行する

```console
$ molecule init role -r apache_vhost
--> Initializing new role apache_vhost...
Initialized role in /Users/answer_d/repos/molecule_test/roles/apache_vhost successfully.
$ cd apache_vhost
```

- こんなかんじのディレクトリが生成される

```console
apache_vhost
├── README.md
├── defaults
│   └── main.yml
├── handlers
│   └── main.yml
├── meta
│   └── main.yml
├── molecule
│   └── default
│       ├── Dockerfile.j2
│       ├── INSTALL.rst
│       ├── molecule.yml
│       ├── playbook.yml
│       └── tests
│           ├── __pycache__
│           │   └── test_default.cpython-38.pyc
│           └── test_default.py
├── tasks
│   └── main.yml
└── vars
    └── main.yml
```

※ この時点では`main.yml`の中身は空

### `molecule/`ディレクトリに、Molecule関連ファイルが入っているので覗いてみる

```console
molecule
└── default
    ├── Dockerfile.j2
    ├── INSTALL.rst
    ├── molecule.yml
    ├── playbook.yml
    └── tests
        ├── __pycache__
        │   └── test_default.cpython-38.pyc
        └── test_default.py
```

- `default/`ディレクトリ
  - これはMoleculeにおいて「シナリオ」と呼ばれる、ロールのテストスイートを示す
  - デフォルトでは`default`ディレクトリが作成されるが、別の名前をつけることもできる
    - `default`以外のシナリオを実行する場合は、`molecule test`コマンドの実行時に明示的にシナリオ名を記述したりする必要がある

- `Dockerfile.j2`
  - Moleculeはこのファイルを使用して、ロールをテストするためのdockerイメージを作成する
  - テスト環境を生成する仕組みをMoleculeでは「ドライバ」と呼び、デフォルトはDockerであるため、このファイルが自動生成される
    - ちなみにDocker以外には、VagrantやEC2、Azureなどが選択できる

  ```jinja
  # Molecule managed

  {% if item.registry is defined %}
  FROM {{ item.registry.url }}/{{ item.image }}
  {% else %}
  FROM {{ item.image }}
  {% endif %}

  {% if item.env is defined %}
  {% for var, value in item.env.items() %}
  {% if value %}
  ENV {{ var }} {{ value }}
  {% endif %}
  {% endfor %}
  {% endif %}

  RUN if [ $(command -v apt-get) ]; then apt-get update && apt-get install -y python sudo bash ca-certificates iproute2 && apt-get clean; \
      elif [ $(command -v dnf) ]; then dnf makecache && dnf --assumeyes install python sudo python-devel python*-dnf bash iproute && dnf clean all; \
      elif [ $(command -v yum) ]; then yum makecache fast && yum install -y python sudo yum-plugin-ovl bash iproute && sed -i 's/plugins=0/plugins=1/g' /etc/yum.conf && yum clean all; \
      elif [ $(command -v zypper) ]; then zypper refresh && zypper install -y python sudo bash python-xml iproute2 && zypper clean -a; \
      elif [ $(command -v apk) ]; then apk update && apk add --no-cache python sudo bash ca-certificates; \
      elif [ $(command -v xbps-install) ]; then xbps-install -Syu && xbps-install -y python sudo bash ca-certificates iproute2 && xbps-remove -O; fi
  ```

- `INSTALL.rst`
  - Moleculeがドライバと正常に接続できるようにするために必要なセットアップ手順が書いてある説明書
  - ただの説明書なのでなくても良い

- `molecule.yml`
  - Moleculeがロールをテストするときの動作を構成したりするための設定ファイル
  - 例えばドライバをDockerから別のものに変更したい場合はこのファイルを書き換えることになる

  ```yaml
  ---
  dependency:
    name: galaxy
  driver:
    name: docker
  lint:
    name: yamllint
  platforms:
    - name: instance
      image: centos:7
  provisioner:
    name: ansible
    lint:
      name: ansible-lint
  verifier:
    name: testinfra
    lint:
      name: flake8
  ```

- `playbook.yml`
  - ロールを呼び出すプレイブック
  - Moleculeはこのプレイブックを`ansible-playbook`で呼び出し、ドライバによって作成されたインスタンスに対して実行する

  ```yaml
  ---
  - name: Converge
    hosts: all
    roles:
      - role: apache_vhost
  ```

- `test/`
  - テストコードを配置するディレクトリ
  - テストツールに何を使用するかは「Verifier」の指定により変更できるが、デフォルトでは[testinfra](https://testinfra.readthedocs.io/en/latest/index.html)であるためこのディレクトリが生成される
  - Verifierはtestinfraのほか、Ansibleなどが選択できる
    - AnsibleをVerifierとする場合はこのディレクトリは不要で、代わりに`verify.yml`を作成する必要がある

### ロールを実装する

上述の教材を信頼し、何も考えず以下のように実装する、`molecule`ディレクトリはまだ触らない  

```console
.
├── files
│   └── index.html
├── handlers
│   └── main.yml
├── tasks
│   └── main.yml
└── templates
    └── vhost.conf.j2
```

```html=files/index.html
simple vhost index
```

```yaml=handlers/main.yml
---
# handlers file for roles/apache_vhost
- name: restart_httpd
  service:
    name: httpd
    state: restarted
```

```yaml=tasks/main.yml
---
- name: install httpd
  yum:
    name: httpd
    state: present

- name: start and enable httpd service
  service:
    name: httpd
    state: started
    enabled: true

- name: ensure vhost directory is present
  file:
    path: "/var/www/vhosts/{{ ansible_hostname }}"
    state: directory

- name: deliver html content
  copy:
    src: index.html
    dest: "/var/www/vhosts/{{ ansible_hostname }}"

- name: template vhost file
  template:
    src: vhost.conf.j2
    dest: /etc/httpd/conf.d/vhost.conf
    owner: root
    group: root
    mode: 0644
  notify:
    - restart_httpd
```

```jinja=templates/vhost.conf.j2
# {{ ansible_managed }}
Listen 8080
<VirtualHost *:8080>
    ServerAdmin webmaster@{{ ansible_fqdn }}
    ServerName {{ ansible_fqdn }}
    ErrorLog logs/{{ ansible_hostname }}-error.log
    CustomLog logs/{{ ansible_hostname }}-common.log common
    DocumentRoot /var/www/vhosts/{{ ansible_hostname }}/

    <Directory /var/www/vhosts/{{ ansible_hostname }}/>
  Options +Indexes +FollowSymlinks +Includes
  Order allow,deny
  Allow from all
    </Directory>
</VirtualHost>
```

### テストを実装する

- 想定するテストケースは以下とする(ちょっと冗長かもだけどあまり気にしない)
  - ポート8080番がオープンである
  - httpdサービスが起動しており、自動起動がオンである
  - index.htmlが取得できる(= ステータスコード200が返ってくる)

- これを実現するtestinfraのコードとして以下を実装
  - テストケースごとに関数作ってassert文を並べるだけなので、python知らない人でも結構書きやすいはず

```python=molecule/default/tests/test_default.py
import os

import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_port_open(host):
    local = host.addr("localhost")

    assert local.port(8080).is_reachable


def test_httpd_enabled_n_started(host):
    httpd_svc = host.service("httpd")

    assert httpd_svc.is_running
    assert httpd_svc.is_enabled


def test_index(host):
    index = host.run("curl -LI http://localhost:8080 -s")

    assert index.rc == 0
    assert "200 OK" in index.stdout.split("\r\n")[0]
```

- プレイブックでserviceモジュールを使っている = Dockerコンテナでsystemctlを触る必要があるため、コンテナの設定を変える
  - `platforms:`に、`privileged: true`と`command: /sbin/init`を追加する
    - 参考 <https://qiita.com/yunano/items/9637ee21a71eba197345>
  - Docker ドライバは内部的に[`ansble_container`モジュール](https://docs.ansible.com/ansible/latest/modules/docker_container_module.html?highlight=docker_container)を使っているのでオプションはこの辺が使えるっぽい

```yaml=molecule/default/molecule.yml
---
dependency:
  name: galaxy
driver:
  name: docker
lint:
  name: yamllint
platforms:
  - name: instance
    image: centos:7
    privileged: true
    command: /sbin/init
provisioner:
  name: ansible
  lint:
    name: ansible-lint
verifier:
  name: testinfra
  lint:
    name: flake8
```

- `Dockerfile.j2`と`playbook.yml`はそのままでOK

### Dockerドライバを使用するため、pipでdockerをインストールする

```console
pip install docker
```

Docker Desktopだけじゃ動かなかった ~~(なんで？)~~

### テストを実行する

```console
$ molecule test
```

これでテストが実行される  
実行結果を上から見ていくと…  

```console
--> Test matrix
    
└── default
    ├── lint
    ├── dependency
    ├── cleanup
    ├── destroy
    ├── syntax
    ├── create
    ├── prepare
    ├── converge
    ├── idempotence
    ├── side_effect
    ├── verify
    ├── cleanup
    └── destroy
```

defaultシナリオが実行されていて、こんな感じのステップで構成されてるよー的なやつ  

#### lint

```console
--> Action: 'lint'
--> Executing Yamllint on files found in /Users/answer_d/repos/molecule_test/roles/apache_vhost/...
Lint completed successfully.
--> Executing Flake8 on files found in /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/default/tests/...
Lint completed successfully.
--> Executing Ansible Lint on /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/default/playbook.yml...
Lint completed successfully.
```

以下の3つのlintが実行されている

- 作成したロール`apache_vhost`に対するYamllint
- testinfraで実装したテストコードに対するFlake8
  - Flake8はpythonのlinter
- `playbook.yml`に対するAnsible Lint

#### create

```console
--> Action: 'create'
    
    PLAY [Create] ******************************************************************
    
    TASK [Log into a Docker registry] **********************************************
    skipping: [localhost] => (item=None) 
    
    TASK [Create Dockerfiles from image names] *************************************
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Determine which docker image info module to use] *************************
    ok: [localhost]
    
    TASK [Discover local Docker images] ********************************************
    ok: [localhost] => (item=None)
    ok: [localhost]
    
    TASK [Build an Ansible compatible image (new)] *********************************
    ok: [localhost] => (item=molecule_local/centos:7)
    
    TASK [Build an Ansible compatible image (old)] *********************************
    skipping: [localhost] => (item=molecule_local/centos:7) 
    
    TASK [Create docker network(s)] ************************************************
    
    TASK [Determine the CMD directives] ********************************************
    ok: [localhost] => (item=None)
    ok: [localhost]
    
    TASK [Create molecule instance(s)] *********************************************
    changed: [localhost] => (item=instance)
    
    TASK [Wait for instance(s) creation to complete] *******************************
    FAILED - RETRYING: Wait for instance(s) creation to complete (300 retries left).
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    PLAY RECAP *********************************************************************
    localhost                  : ok=7    changed=3    unreachable=0    failed=0    skipped=3    rescued=0    ignored=0
    
```

Dockerfileからイメージを作って、Dockerコンテナを作成している  
Moleculeが内部的に持つプレイブックで実行されていることがわかる  

#### conerge

```console
--> Action: 'converge'
    
    PLAY [Converge] ****************************************************************
    
    TASK [Gathering Facts] *********************************************************
    ok: [instance]
    
    TASK [apache_vhost : install httpd] ********************************************
    changed: [instance]
    
    TASK [apache_vhost : start and enable httpd service] ***************************
    changed: [instance]
    
    TASK [apache_vhost : ensure vhost directory is present] ************************
    changed: [instance]
    
    TASK [apache_vhost : deliver html content] *************************************
    changed: [instance]
    
    TASK [apache_vhost : template vhost file] **************************************
    changed: [instance]
    
    RUNNING HANDLER [apache_vhost : restart_httpd] *********************************
    changed: [instance]
    
    PLAY RECAP *********************************************************************
    instance                   : ok=7    changed=6    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

自分が作ったロールを先程作成したインスタンスに対して実行している

#### idempotence

```console
--> Action: 'idempotence'
Idempotence completed successfully.
```

結果からは見えにくいが、ここで冪等性の確認を行っている(idempotenceは「冪等性」という意味)  
convergeで実行したプレイブックをもう一度実行し、changedステータスが返らないことを検証しているらしい

#### verify

```console
--> Action: 'verify'
--> Executing Testinfra tests found in /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/default/tests/...
    ============================= test session starts ==============================
    platform darwin -- Python 3.8.0, pytest-5.3.2, py-1.8.1, pluggy-0.13.1
    rootdir: /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/default
    plugins: testinfra-3.4.0
collected 3 items                                                              
    
    tests/test_default.py ...                                                [100%]
    
    ============================== 3 passed in 2.64s ===============================
Verifier completed successfully.
```

testinfraコードをインスタンス上で実行する
3件テストし、全てパスしていることが確認できる

#### destroy

```console
--> Action: 'destroy'
    
    PLAY [Destroy] *****************************************************************
    
    TASK [Destroy molecule instance(s)] ********************************************
    changed: [localhost] => (item=instance)
    
    TASK [Wait for instance(s) deletion to complete] *******************************
    FAILED - RETRYING: Wait for instance(s) deletion to complete (300 retries left).
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Delete docker network(s)] ************************************************
    
    PLAY RECAP *********************************************************************
    localhost                  : ok=2    changed=2    unreachable=0    failed=0    skipped=1    rescued=0    ignored=0
    
--> Pruning extra files from scenario ephemeral directory
```

テストに使用したインスタンスを削除する

### できた

これでわたしもMoleculer  

今回は一発で成功する例を示しましたが、プレイブックに意図的に変な空白を入れてみたり、プレイブックやテストコードの処理内容を変えてみたりすることでエラーが検出できることを確認できます、興味があればやってみて下さい  

## おまけ

- `molecule test`で実行される一部のステップだけ取り出して実行することもできる
  - `molecule create`: dependency, create, prepare
    - インスタンスが作成されるとこまで
  - `molecule converge`: dependency, create, prepare, converge
    - create+Playbookの実行まで
  - `molecule destroy`: dependency, cleanup, destroy
    - インスタンスの削除
- なのでテスト自動化前提でなくて、ロールを作るだけでも結構うれしい、Dockerコンテナ上げて動作テストしながらーって手でやるとまぁまぁ手間だけど、Moleculeならいい感じにしてくれていい感じ(語彙力)
  - 作ったコンテナにログインしてくれる`molecule login`とかもある(`vagrant ssh`みたいな感じで使える)
  - サーバの状態確認するときラクラクの楽になって便利

- VerifierはAnsibleにすることもできる
  - testinfraだとpythonコードになってしまうので、プログラムかけないインフラマンはAnsibleをVerifierにするととっつきやすい
    - といってもtestinfraだけだったらpythonでも十分書きやすいと思われるのでぶっちゃけどっちでも良いと思う、好みとテストでやりたいこと次第で決めれば良い
  - AnsibleをVerifierにした場合でも、テスト用モジュールはちゃんとある
    - ポートチェックとかどうやるの？って思ったら[`wait_for`モジュール](https://docs.ansible.com/ansible/latest/modules/wait_for_module.html)とかあった、さすがです

ちなみにAnsibleをVerifierにする場合、今回作成したtestinfraと同様のテストを行うプレイブックは以下のようになる  
このファイルを用意して、`molecule/default/molecule.yml`でVerifierにAnsibleを使用する旨を記載するとAnsibleでテストするようになるので気になる人は試してみると良い  

```yaml=molecule/default/verify.yml
---
- name: Verify
  hosts: all
  gather_facts: false
  pre_tasks:
    - name: get httpd status
      service_facts:

    - name: get index.html
      uri:
        url: http://localhost:8080
        method: GET
      register: response

  tasks:
    - name: test port 8080 open
      wait_for:
        port: 8080
        timeout: 5

    - name: test http enabled and started
      assert:
        that:
          - ansible_facts.services['httpd.service'].state == "running"
          - ansible_facts.services['httpd.service'].status == "enabled"

    - name: test httpd returns status 200 and has content
      assert:
        that:
          - response.status == 200
          - response.content is not none
```
