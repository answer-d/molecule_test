# Moleculeお勉強マン

## 入門

- Qiita投稿済
  - [Moleculeに入門してみたよ](https://qiita.com/answer_d/items/0119669f2e6151a86fc3)

## Dockerドライバで複数イメージを同時に使う

インスタンスは`molecule.yml`に配列で書けるようになっているので、複数用意したければ並べて書く

```yaml:molecule.yml
platforms:
  - name: centos7
    image: centos:7
    privileged: true
    command: /sbin/init
  - name: centos6
    image: centos:6
    privileged: true
    command: /sbin/init
```

複数インスタンスを定義して`molecule test`すると、同時に複数インスタンスに対して処理が行われる

```log
--> Action: 'converge'

    PLAY [Converge] ****************************************************************

    TASK [Gathering Facts] *********************************************************
    ok: [centos7]
    ok: [centos6]

    TASK [apache_vhost : install httpd] ********************************************
    changed: [centos6]
    changed: [centos7]

    TASK [apache_vhost : start and enable httpd service] ***************************
    changed: [centos6]
    changed: [centos7]
```

テストケースを分ける場合はテストコード内で頑張る

```yaml:verify.yml
    - name: test http enabled and started (centos7)
      assert:
        that:
          - ansible_facts.services['httpd.service'].state == "running"
          - ansible_facts.services['httpd.service'].status == "enabled"
      when:
        - ansible_facts.distribution == "CentOS"
        - ansible_facts.distribution_major_version == "7"
    - name: test http enabled and started (centos6)
      assert:
        that:
          - ansible_facts.services.httpd.state == "running"
          - ansible_facts.services.httpd.status == "enabled"
      when:
        - ansible_facts.distribution == "CentOS"
        - ansible_facts.distribution_major_version == "6"
```

VerifierがAnsibleの場合は実行対象ホストの定義をインスタンス名にしてあげても良さげ

```yaml:verify.yml
- name: Verify centos7 instance only
  hosts: centos7
  tasks:
    - name: cent7 only
      debug:
        msg: "i am {{ ansible_host }}"
```

testinfraの場合はどうするんだろう…？

## Driverを変えてみる

### Vagrant

<https://molecule.readthedocs.io/en/stable/configuration.html#vagrant>

- `pip install vagrant`

```yaml:molecule.yml
---
dependency:
  name: galaxy
driver:
  name: vagrant
  provider:
    name: virtualbox
lint:
  name: yamllint
platforms:
  - name: instance
    box: centos/7
    box_version: "1905.1"
    memory: 1024
    cpus: 1
provisioner:
  name: ansible
  lint:
    name: ansible-lint
verifier:
  name: ansible
  lint:
    name: ansible-lint
```

```yaml:playbook.yml
---
- name: Converge
  hosts: all
  become: true
  roles:
    - role: apache_vhost
```

そもそもdockerがDriverでも`become: true`しておくべきだったな

- `verify.yml` は一緒

- ていうかそもそも`molecule init scenario -s driver_vagrant -d vagrant`みたいにしたらドライバ指定しながらシナリオ作れたわ
- `--verifier_name`でverifierの指定もできたわwwなるほどなーww

### ec2

```console
$ molecule init scenario -s driver_ec2 -d ec2 --verifier-name ansible
```

#### 生成されたやつ読む

##### `molecule`ディレクトリ構成

```plaintext
molecule/driver_ec2/
├── INSTALL.rst
├── create.yml
├── destroy.yml
├── molecule.yml
├── playbook.yml
├── prepare.yml
└── verify.yml
```

##### create.yml

```yaml
---
- name: Create
  hosts: localhost
  connection: local
  gather_facts: false
  no_log: "{{ molecule_no_log }}"
  vars:
    ssh_user: ubuntu
    ssh_port: 22

    security_group_name: molecule
    security_group_description: Security group for testing Molecule
    security_group_rules:
      - proto: tcp
        from_port: "{{ ssh_port }}"
        to_port: "{{ ssh_port }}"
        cidr_ip: '0.0.0.0/0'
      - proto: icmp
        from_port: 8
        to_port: -1
        cidr_ip: '0.0.0.0/0'
    security_group_rules_egress:
      - proto: -1
        from_port: 0
        to_port: 0
        cidr_ip: '0.0.0.0/0'

    keypair_name: molecule_key
    keypair_path: "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}/ssh_key"
  tasks:
    - name: Create security group
      ec2_group:
        name: "{{ security_group_name }}"
        description: "{{ security_group_name }}"
        rules: "{{ security_group_rules }}"
        rules_egress: "{{ security_group_rules_egress }}"

    - name: Test for presence of local keypair
      stat:
        path: "{{ keypair_path }}"
      register: keypair_local

    - name: Delete remote keypair
      ec2_key:
        name: "{{ keypair_name }}"
        state: absent
      when: not keypair_local.stat.exists

    - name: Create keypair
      ec2_key:
        name: "{{ keypair_name }}"
      register: keypair

    - name: Persist the keypair
      copy:
        dest: "{{ keypair_path }}"
        content: "{{ keypair.key.private_key }}"
        mode: 0600
      when: keypair.changed

    - name: Get the ec2 ami(s) by owner and name, if image not set
      ec2_ami_facts:
        owners: "{{ item.image_owner }}"
        filters:
          name: "{{ item.image_name }}"
      loop: "{{ molecule_yml.platforms }}"
      when: item.image is not defined
      register: ami_facts

    - name: Create molecule instance(s)
      ec2:
        key_name: "{{ keypair_name }}"
        image: "{{ item.image
          if item.image is defined
          else (ami_facts.results[index].images | sort(attribute='creation_date', reverse=True))[0].image_id }}"
        instance_type: "{{ item.instance_type }}"
        vpc_subnet_id: "{{ item.vpc_subnet_id }}"
        group: "{{ security_group_name }}"
        instance_tags: "{{ item.instance_tags | combine({'instance': item.name})
          if item.instance_tags is defined
          else {'instance': item.name} }}"
        wait: true
        assign_public_ip: true
        exact_count: 1
        count_tag:
          instance: "{{ item.name }}"
      register: server
      loop: "{{ molecule_yml.platforms }}"
      loop_control:
        index_var: index
      async: 7200
      poll: 0

    - name: Wait for instance(s) creation to complete
      async_status:
        jid: "{{ item.ansible_job_id }}"
      register: ec2_jobs
      until: ec2_jobs.finished
      retries: 300
      with_items: "{{ server.results }}"

    # Mandatory configuration for Molecule to function.

    - name: Populate instance config dict
      set_fact:
        instance_conf_dict: {
          'instance': "{{ item.instances[0].tags.instance }}",
          'address': "{{ item.instances[0].public_ip }}",
          'user': "{{ ssh_user }}",
          'port': "{{ ssh_port }}",
          'identity_file': "{{ keypair_path }}",
          'instance_ids': "{{ item.instance_ids }}", }
      with_items: "{{ ec2_jobs.results }}"
      register: instance_config_dict
      when: server.changed | bool

    - name: Convert instance config dict to a list
      set_fact:
        instance_conf: "{{ instance_config_dict.results | map(attribute='ansible_facts.instance_conf_dict') | list }}"
      when: server.changed | bool

    - name: Dump instance config
      copy:
        content: "{{ instance_conf | to_json | from_json | molecule_to_yaml | molecule_header }}"
        dest: "{{ molecule_instance_config }}"
      when: server.changed | bool

    - name: Wait for SSH
      wait_for:
        port: "{{ ssh_port }}"
        host: "{{ item.address }}"
        search_regex: SSH
        delay: 10
        timeout: 320
      with_items: "{{ lookup('file', molecule_instance_config) | molecule_from_yaml }}"

    - name: Wait for boot process to finish
      pause:
        minutes: 2
```

##### destroy.yml

```yaml
---
- name: Destroy
  hosts: localhost
  connection: local
  gather_facts: false
  no_log: "{{ molecule_no_log }}"
  tasks:
    - block:
        - name: Populate instance config
          set_fact:
            instance_conf: "{{ lookup('file', molecule_instance_config) | molecule_from_yaml }}"
            skip_instances: false
      rescue:
        - name: Populate instance config when file missing
          set_fact:
            instance_conf: {}
            skip_instances: true

    - name: Destroy molecule instance(s)
      ec2:
        state: absent
        instance_ids: "{{ item.instance_ids }}"
      register: server
      with_items: "{{ instance_conf }}"
      when: not skip_instances
      async: 7200
      poll: 0

    - name: Wait for instance(s) deletion to complete
      async_status:
        jid: "{{ item.ansible_job_id }}"
      register: ec2_jobs
      until: ec2_jobs.finished
      retries: 300
      with_items: "{{ server.results }}"

    # Mandatory configuration for Molecule to function.

    - name: Populate instance config
      set_fact:
        instance_conf: {}

    - name: Dump instance config
      copy:
        content: "{{ instance_conf | to_json | from_json | molecule_to_yaml | molecule_header }}"
        dest: "{{ molecule_instance_config }}"
      when: server.changed | bool
```

##### molecule.yml

```yaml
---
dependency:
  name: galaxy
driver:
  name: ec2
lint:
  name: yamllint
platforms:
  - name: instance
    image: ami-a5b196c0
    instance_type: t2.micro
    vpc_subnet_id: subnet-6456fd1f
provisioner:
  name: ansible
  lint:
    name: ansible-lint
verifier:
  name: ansible
  lint:
    name: ansible-lint
```

- <https://molecule.readthedocs.io/en/stable/configuration.html#ec2>
  - Ansibleのec2モジュールを使うらしい
- ここではimage idを指定してあるけど、`create.yml`をみると、`image_owner`と`image_name`を指定する方式も取れそう(AMI IDはec2_ami_factsモジュールで拾っているみたい)

##### playbook.yml

```yaml
---
- name: Converge
  hosts: all
  roles:
    - role: apache_vhost
```

- これはまぁ普通

##### prepare.yml

```yaml
---
- name: Prepare
  hosts: all
  gather_facts: false
  tasks:
    - name: Install python for Ansible
      raw: test -e /usr/bin/python || (apt -y update && apt install -y python-minimal python-zipstream)
      become: true
      changed_when: false
```

- これもいつものってかんじ

#### やってみよー

##### アクセスキーの設定

- ec2モジュールでのアクセスキーの扱い方
  - <https://docs.ansible.com/ansible/latest/modules/ec2_module.html#notes>
- Playbookのパラメータに直接書いてもいいけど、環境変数に設定してもOK、なので以下のような感じで設定しておく

```console
$ echo $AWS_ACCESS_KEY_ID
AKIA****
$ echo $AWS_SECRET_ACCESS_KEY
****
$ echo $AWS_REGION
ap-northeast-1
```

##### サブネットの作成と設定

- AWSでVPCとサブネットを作る(手順は割愛)
- EC2インスタンスを配置したいサブネットのIDを`vpc_subnet_id`に書く

##### 使用するイメージの設定

```yaml:molecule.yml
platforms:
  - name: instance
    image_owner: amazon
    image_name: amzn2-ami-hvm-2.*-x86_64-gp2
    instance_type: t2.micro
    vpc_subnet_id: subnet-0072a021e34ddd8ea
```

##### セキュリティグループ周りの設定変更

- sshユーザ変更(デフォルトは`ubuntu`)

```yaml:create.yml
  vars:
    ssh_user: ec2-user
    ssh_port: 22
```

- デフォルトVPCが存在する必要があったのでVPC消して作り直した
  - デフォルトVPCでなくても`create.yml`に`vpc_id`パラメータ追加すればなんとでもなる感じ

```yaml
    - name: Create security group
      ec2_group:
        name: "{{ security_group_name }}"
        description: "{{ security_group_name }}"
        rules: "{{ security_group_rules }}"
        rules_egress: "{{ security_group_rules_egress }}"
```

##### `create`シナリオ実行してインスタンスできること確認

- prepareフェーズまで流れたので、ssh接続もOK
- でも鍵の受け渡しってどうやってるんだろ…

```yaml:create.yml
    keypair_name: molecule_key
    keypair_path: "{{ lookup('env', 'MOLECULE_EPHEMERAL_DIRECTORY') }}/ssh_key"
```

- この変数情報で作ってるっぽいけど…どこにあるんだ？
  - ここだった `~/.cache/molecule/apache_vhost/driver_ec2/ssh_key`

```yaml:create.yml
    - name: Create keypair
      ec2_key:
        name: "{{ keypair_name }}"
      register: keypair

    - name: Persist the keypair
      copy:
        dest: "{{ keypair_path }}"
        content: "{{ keypair.key.private_key }}"
        mode: 0600
      when: keypair.changed
```

- ここの処理で作りながらローカルに持ってきてるみたい、Ansibleならこれができるのか…すごい…CloudFormationじゃ無理だな…
- 一度作成されてる状態でcreateを再実行すると消して作り直すっぽい、同時に複数人がテストして、鍵を引っ張る前に消さなければ大丈夫って感じ？

- `create.yml`の一番最後にブート待ちで2分ウェイトする処理が入ってるので注意したい

##### テストやってみる

```console
$ molecule test -s driver_ec2
--> Validating schema /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/driver_ec2/molecule.yml.
Validation completed successfully.
--> Validating schema /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/default/molecule.yml.
Validation completed successfully.
--> Validating schema /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/driver_vagrant/molecule.yml.
Validation completed successfully.
--> Test matrix
    
└── driver_ec2
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
    
--> Scenario: 'driver_ec2'
--> Action: 'lint'
--> Executing Yamllint on files found in /Users/answer_d/repos/molecule_test/roles/apache_vhost/...
Lint completed successfully.
--> Executing Ansible Lint on /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/driver_ec2/verify.yml...
Lint completed successfully.
--> Executing Ansible Lint on /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/driver_ec2/playbook.yml...
Lint completed successfully.
--> Scenario: 'driver_ec2'
--> Action: 'dependency'
Skipping, missing the requirements file.
--> Scenario: 'driver_ec2'
--> Action: 'cleanup'
Skipping, cleanup playbook not configured.
--> Scenario: 'driver_ec2'
--> Action: 'destroy'
    
    PLAY [Destroy] *****************************************************************
    
    TASK [Populate instance config] ************************************************
    ok: [localhost]
    
    TASK [Destroy molecule instance(s)] ********************************************
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Wait for instance(s) deletion to complete] *******************************
    FAILED - RETRYING: Wait for instance(s) deletion to complete (300 retries left).
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Populate instance config] ************************************************
    ok: [localhost]
    
    TASK [Dump instance config] ****************************************************
    changed: [localhost]
    
    PLAY RECAP *********************************************************************
    localhost                  : ok=5    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
    
--> Scenario: 'driver_ec2'
--> Action: 'syntax'
    
    playbook: /Users/answer_d/repos/molecule_test/roles/apache_vhost/molecule/driver_ec2/playbook.yml
--> Scenario: 'driver_ec2'
--> Action: 'create'
    
    PLAY [Create] ******************************************************************
    
    TASK [debug] *******************************************************************
    ok: [localhost]
    
    TASK [Create security group] ***************************************************
    ok: [localhost]
    
    TASK [Test for presence of local keypair] **************************************
    ok: [localhost]
    
    TASK [Delete remote keypair] ***************************************************
    skipping: [localhost]
    
    TASK [Create keypair] **********************************************************
    ok: [localhost]
    
    TASK [Persist the keypair] *****************************************************
    skipping: [localhost]
    
    TASK [Get the ec2 ami(s) by owner and name, if image not set] ******************
    ok: [localhost] => (item=None)
    ok: [localhost]
    
    TASK [Create molecule instance(s)] *********************************************
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Wait for instance(s) creation to complete] *******************************
    FAILED - RETRYING: Wait for instance(s) creation to complete (300 retries left).
    FAILED - RETRYING: Wait for instance(s) creation to complete (299 retries left).
    FAILED - RETRYING: Wait for instance(s) creation to complete (298 retries left).
    FAILED - RETRYING: Wait for instance(s) creation to complete (297 retries left).
    FAILED - RETRYING: Wait for instance(s) creation to complete (296 retries left).
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Populate instance config dict] *******************************************
    ok: [localhost] => (item=None)
    ok: [localhost]
    
    TASK [Convert instance config dict to a list] **********************************
    ok: [localhost]
    
    TASK [Dump instance config] ****************************************************
    changed: [localhost]
    
    TASK [Wait for SSH] ************************************************************
    ok: [localhost] => (item=None)
    ok: [localhost]
    
    TASK [Wait for boot process to finish] *****************************************
    Pausing for 120 seconds
    (ctrl+C then 'C' = continue early, ctrl+C then 'A' = abort)
    ok: [localhost]
    
    PLAY RECAP *********************************************************************
    localhost                  : ok=12   changed=3    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
    
--> Scenario: 'driver_ec2'
--> Action: 'prepare'
    
    PLAY [Prepare] *****************************************************************
    
    TASK [Install python for Ansible] **********************************************
    ok: [instance]
    
    PLAY RECAP *********************************************************************
    instance                   : ok=1    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
    
--> Scenario: 'driver_ec2'
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
    
--> Scenario: 'driver_ec2'
--> Action: 'idempotence'
Idempotence completed successfully.
--> Scenario: 'driver_ec2'
--> Action: 'side_effect'
Skipping, side effect playbook not configured.
--> Scenario: 'driver_ec2'
--> Action: 'verify'
--> Running Ansible Verifier
    
    PLAY [Verify] ******************************************************************
    
    TASK [Gathering Facts] *********************************************************
    ok: [instance]
    
    TASK [Example assertion] *******************************************************
    ok: [instance] => {
        "changed": false,
        "msg": "All assertions passed"
    }
    
    PLAY RECAP *********************************************************************
    instance                   : ok=2    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
    
Verifier completed successfully.
--> Scenario: 'driver_ec2'
--> Action: 'cleanup'
Skipping, cleanup playbook not configured.
--> Scenario: 'driver_ec2'
--> Action: 'destroy'
    
    PLAY [Destroy] *****************************************************************
    
    TASK [Populate instance config] ************************************************
    ok: [localhost]
    
    TASK [Destroy molecule instance(s)] ********************************************
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Wait for instance(s) deletion to complete] *******************************
    FAILED - RETRYING: Wait for instance(s) deletion to complete (300 retries left).
    changed: [localhost] => (item=None)
    changed: [localhost]
    
    TASK [Populate instance config] ************************************************
    ok: [localhost]
    
    TASK [Dump instance config] ****************************************************
    changed: [localhost]
    
    PLAY RECAP *********************************************************************
    localhost                  : ok=5    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
    
--> Pruning extra files from scenario ephemeral directory
```
