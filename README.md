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
