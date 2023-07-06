# Contributing

The Import/Export Tool for VMware Cloud on AWS team welcomes contributions from the community.

Before you start working with the VMware Event Broker Appliance, please read our [Developer Certificate of Origin](https://cla.vmware.com/dco){:target="_blank"}. All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch.

# Preqrequisites

Two tools are required in order to contribute code - You must install [Git](https://git-scm.com/downloads){:target="_blank"} and [Python](https://www.python.org/downloads/){:target="_blank"}

You must also create a [Github](https://github.com/join){:target="_blank"} account. You need to verify your email with Github in order to contribute to the VEBA repository.

# Quickstart for Contributing

## Download the Import/Export tool source code
```bash
git clone https://github.com/vmware-samples/sddc-import-export-for-vmware-cloud-on-aws.git
```

## Configure git to sign code with your verified name and email
```bash
git config --global user.name "Your Name"
git config --global user.email "youremail@domain.com"
```

## Contribute documentation changes

Make the necessary changes and save your files. 
```bash
git diff
```

This is sample output from git. It will show you files that have changed as well as all display all changes.
```bash
user@wrkst01 MINGW64 ~/Documents/git/vcenter-event-broker-appliance(master)
$ git diff
diff --git a/docs/kb/contribute-start.md b/docs/kb/contribute-start.md
index 4245046..f86f09f 100644
--- a/docs/kb/contribute-start.md
+++ b/docs/kb/contribute-start.md
@@ -6,6 +6,32 @@ description: Getting Started
 permalink: /kb/contribute-start
 ---
```
Commit the code and push your commit. -a commits all changed files, -s signs your commit, and -m is a commit message - a short description of your change.


```bash
git commit -a -s -m "Added prereq and git diff output to contribution page."
git push
```

You can then submit a pull request (PR) to the maintainers - a step-by-step guide with screenshots is available [here](http://www.patrickkremer.com/2019/12/vcenter-event-broker-appliance-part-v-contributing-to-the-veba-project/){:target="_blank"}.


## Submitting Bug Reports and Feature Requests

Please submit bug reports and feature requests by using our GitHub [Issues](https://github.com/vmware-samples/sddc-import-export-for-vmware-cloud-on-aws/issues){:target="_blank"} page.

Before you submit a bug report about the code in the repository, please check the Issues page to see whether someone has already reported the problem. In the bug report, be as specific as possible about the error and the conditions under which it occurred. On what version and build did it occur? What are the steps to reproduce the bug?

Feature requests should fall within the scope of the project.

## Pull Requests

Before submitting a pull request, please make sure that your change satisfies the following requirements:
- The change is signed as described by the [Developer Certificate of Origin](https://cla.vmware.com/dco){:target="_blank"} doc.
- The change is clearly documented and follows Git commit [best practices](https://chris.beams.io/posts/git-commit/){:target="_blank"}
