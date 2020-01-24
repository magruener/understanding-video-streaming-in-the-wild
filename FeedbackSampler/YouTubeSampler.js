sample_dictionary = {
        'timestamp' : [],
        'paused' : [],
        'videoWidth' : [],
        'videoHeight' : [],
        'decodedFrames' : [],
        'droppedFrames' : [],
        'played_until' : [],
        'buffered_until' : [],
};

VideoPlayer = document.getElementById('movie_player');
player = document.querySelector('div video');

sampleYouTubeState = function () {
    sample_dictionary['timestamp'].push(Date.now());
    sample_dictionary['paused'].push(player.paused);
    sample_dictionary['videoWidth'].push(player.videoWidth);
    sample_dictionary['videoHeight'].push( player.videoHeight);
    sample_dictionary['decodedFrames'].push(player.webkitDecodedFrameCount);
    sample_dictionary['droppedFrames'].push(player.webkitDroppedFrameCount);
    try{
        sample_dictionary['played_until'].push(player.played.end(player.played.length - 1));
        sample_dictionary['buffered_until'].push(player.buffered.end(player.buffered.length - 1));
    }catch (e) {
        sample_dictionary['played_until'].push(0);
        sample_dictionary['buffered_until'].push(0);
    }

    setTimeout(sampleYouTubeState, 1000);
};

getLastState = function (){
    ts = sample_dictionary['timestamp'][sample_dictionary['timestamp'].length -1];
    paused = sample_dictionary['paused'][sample_dictionary['paused'].length -1];
    videoWidth = sample_dictionary['videoWidth'][sample_dictionary['videoWidth'].length -1];
    videoHeight = sample_dictionary['videoHeight'][sample_dictionary['videoHeight'].length -1];
    decodedFrames = sample_dictionary['decodedFrames'][sample_dictionary['decodedFrames'].length -1];
    droppedFrames = sample_dictionary['droppedFrames'][sample_dictionary['droppedFrames'].length -1];
    played_until = sample_dictionary['played_until'][sample_dictionary['played_until'].length -1];
    buffered_until =sample_dictionary['buffered_until'][sample_dictionary['buffered_until'].length -1];
    return [ts, paused, played_until, buffered_until, videoWidth, videoHeight, decodedFrames,
                droppedFrames]
};

//sampleYouTubeState();