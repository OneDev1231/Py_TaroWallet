



while true
do
    echo "checking..."
    minutes=$(date +"%M")
    if [ $(( minutes % 10 )) == 6 ]; then
        now=$(printf "%(%F_%H%M)T") 
        echo "Backup data for date $now..."
        echo "dumping DB..."
        python manage.py dumpdata --indent 2 > db_backup.json
        aws s3 cp ~/db_backup.json s3://node-backup-bucket/prod_backup/$now/db_backup.json
        aws s3 cp --recursive ~/.lnd/ s3://node-backup-bucket/prod_backup/$now/.lnd/  
        aws s3 cp --recursive ~/.tapd/ s3://node-backup-bucket/prod_backup/$now/.tapd/ 
        aws s3 cp --recursive ~/.bitcoin/ s3://node-backup-bucket/prod_backup/$now/.bitcoin/ 
        echo "Sleeping for 10 minutes..."
    fi
    sleep 60
done
