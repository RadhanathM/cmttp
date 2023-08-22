if [ "$TOTAL_TEST_DURATION" -eq 0 ];then
    /root/Sipp_3.2/sipp.svn/sipp -m $TOTAL_CALLS -l $MAX_SIMULTANEOUS_CALL -i $LOCAL_SIP_IP $REMOTE_SIP_IP:$REMOTE_SIP_PORT -p $LOCAL_IPA_SIP_PORT -sf IPASenderAuth.xml -trace_msg -trace_err -trace_logs -trace_screen -nd -inf preestablishedseq.csv -inf termmdn.csv -inf origmdn.csv -r $CALL_RATE
else
    /root/Sipp_3.2/sipp.svn/sipp -l $MAX_SIMULTANEOUS_CALL -i $LOCAL_SIP_IP $REMOTE_SIP_IP:$REMOTE_SIP_PORT -p $LOCAL_IPA_SIP_PORT -sf IPASenderAuth.xml -trace_msg -trace_err -trace_logs -trace_screen -nd -inf preestablishedseq.csv -inf termmdn.csv -inf origmdn.csv -r $CALL_RATE -timeout $TOTAL_TEST_DURATION
fi
