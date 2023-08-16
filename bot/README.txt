HOWTO
- you need a Toolforge account that is in the service group of 'pb': https://pb.toolforge.org/
- The bot source code is located under https://github.com/euku/spbot/tree/spbot/scripts/userscripts/pers-bek*.py -> branch spbot
- Check your bot & update the file path to the pyapi (https://github.com/tool-labs/pb/blob/master/pyapi/wppb.py)
- Load the jobs for WP:PB into Toolforge's job framework, see https://wikitech.wikimedia.org/wiki/Help:Toolforge/Jobs_framework
  The file is shared at
      https://github.com/euku/spbot/blob/51b6efff1446b3240987cca22957a1159ec3d4ce/jobs/toolforge-jobs.yaml
  but contains all of SpBot's jobs.
