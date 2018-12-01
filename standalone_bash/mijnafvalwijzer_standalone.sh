#!/bin/bash

##### Functions
function usage {
    echo -e "\nusage: $0 [--postcode <value> --huisnummer <value>][--output <filename>][--debug][--help]"
    echo -e ""
    echo -e "  General parameters:"
    echo -e "    --postcode       specify postcal code."
    echo -e "    --huisnummer     specify house number."
    echo -e "    --output         specify output file. Default: mijnafvalwijzer.json"
    echo -e "    --debug          debug mode."
    echo -e "    -?               help."
    exit 0
}

function commands_check {
  for i; do
    if command -v $i >/dev/null 2>&1; then
      true
    else
      echo "This script requires '$i'"
      false
    fi
  done || exit 1
}

##### Posistional params
while [ $# -gt 0 ]; do
    case $1 in
      --postcode )     shift && export POSTCODE="$1" ;;
      --huisnummer )   shift && export HUISNUMMER="$1" ;;
      --output )       shift && export OUTPUT="$1" ;;
      --debug )        DEBUG=debug ;;
      -? | --help )    usage && exit 0 ;;
      * )              echo -e "\nError: Unknown option: $1\n" >&2 && exit 1 ;;
    esac
    shift
done

##### Main
if [[ ! -z $DEBUG ]]; then set -x; fi
if [[ -z $POSTCODE ]]; then echo "Postcode missing!"; usage; fi
if [[ -z $HUISNUMMER ]]; then echo "Huisnummer missing!"; usage; fi
if [[ -z $OUTPUT ]]; then export OUTPUT="mijnafvalwijzer.json"; fi

commands_check curl jq

curl -Ssl "https://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode=${POSTCODE}&street=&huisnummer=${HUISNUMMER}" | jq -rc ".data.ophaaldagen.data" > ${OUTPUT}
[ -s ${OUTPUT} ] || curl -Ssl "http://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode=${POSTCODE}&street=&huisnummer=${HUISNUMMER}" | jq -rc ".data.ophaaldagenNext.data" > ${OUTPUT}


ALL_TRASH_TYPES=$(cat ${OUTPUT} | jq -rc ". | unique_by(.type)[].type")
FUTURE_TRASH_TYPES=$(cat ${OUTPUT} | jq -rc "[.[] | select(.date >= \"$(date +%Y-%m-%d)\")] | unique_by(.type)[].type")

for TRASH_TYPE in ${FUTURE_TRASH_TYPES}; do
  cat ${OUTPUT} | jq -rc "[.[] | select(.date >= \"$(date +%Y-%m-%d)\" and .type == \"${TRASH_TYPE}\")][0]"
done

 
#ALL_TRASH_TYPES=$(curl -Ssl "http://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode=${POSTCODE}&street=&huisnummer=${HUISNUMMER}" | jq -rc ".data.ophaaldagen.data | unique_by(.type)[].type")
#FUTURE_TRASH_TYPES=$(curl -Ssl "http://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode=${POSTCODE}&street=&huisnummer=${HUISNUMMER}" | jq -rc "[.data.ophaaldagen.data[] | select(.date >= \"$(date +%Y-%m-%d)\")] | unique_by(.type)[].type")

#for TRASH_TYPE in ${FUTURE_TRASH_TYPES}; do
#  curl -Ssl "http://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode=${POSTCODE}&street=&huisnummer=${HUISNUMMER}" | jq -rc "[.data.ophaaldagen.data[] | select(.date >= \"$(date +%Y-%m-%d)\" and .type == \"${TRASH_TYPE}\")][0]"
#done  
