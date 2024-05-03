#! /bin/bash
set -e

ids=(
    US20230418876 # test patent
    KR101863193B1 # IoT cat self-cleaning toilet
    US20080270152A1 # Patent trolling
    US6360693B1 # A stick
    US5443036A # Using a laser pointer to exercise a cat
    CN117151338A # Multi-unmanned aerial vehicle task planning method based on large language model
    CN109255113B # Intelligent proofreading system
)


demo_dir="/tmp/demo"
mkdir -p $demo_dir

for id in "${ids[@]}"
do
    echo "Fetching ${id}"
    patent_fetcher $id > "$demo_dir/$id.json"
done

echo "Done"
