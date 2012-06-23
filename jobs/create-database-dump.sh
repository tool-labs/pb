#! /bin/bash
#$ -j y
#$ -o $HOME/create-database-dump.out

DB_NAME="p_wppb_trunk"
HOST="sql-s2-user"
DATE=`date +%Y-%m-%d`

OUTPUT_DIRECTORY="/home/project/w/p/p/wppb/public_html/sql-dumps/"

if [[ $# > 0 ]] ; then
  echo "using database name $1"
  DB_NAME="$1"
fi

if [[ $# > 1 ]] ; then
  echo "using host name $2"
  HOST="$2"
fi

if [[ $# > 2 ]] ; then
  echo "using output directory $3"
  OUTPUT_DIRECTORY="$3"
fi

if [[ ! -d $OUTPUT_DIRECTORY ]] ; then
  echo "The output directory $OUTPUT_DIRECTORY does not exist. Aborting."
  exit 2
fi

if [[ ! -w $OUTPUT_DIRECTORY ]] ; then
  echo "The output directory $OUTPUT_DIRECTORY is not writable. Aborting."
  exit 3
fi

OUTPUT_FILE_NAME="$DB_NAME-$DATE.sql"

echo "Creating dump of $DB_NAME on $HOST for $DATE"
mysqldump -h$HOST $DB_NAME > $OUTPUT_DIRECTORY$OUTPUT_FILE_NAME

if [[ $? != 0 ]] ; then
  echo "Could not create dump."
  exit 1
fi


echo "Zipping dump file"
cd $OUTPUT_DIRECTORY && bzip2 --compress $OUTPUT_FILE_NAME

if [[ $? != 0 ]] ; then
  echo "Could not zip dump file."
  exit 4
fi

echo "Successfully created and zipped dump file $OUTPUT_DIRECTORY$OUTPUT_FILE_NAME.bz2"
