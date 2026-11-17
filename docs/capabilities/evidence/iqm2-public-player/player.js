var jwMediaPlayer;
var playerStartPosition;

var types = {
    ".mp4": "video/mp4",
    ".m3u8": "application/x-mpegURL"
}
$(function () {
    $(document).on('click', '#liveButton', function (e) {
        e.preventDefault();
    });
});
function SetupJWPlayer(playSources, enableDVR, hasTranscript) {
    if (enableDVR === undefined || enableDVR == "False") {
        enableDVR = false;
    }

    if (hasTranscript === undefined || hasTranscript == "False") {
        hasTranscript = false;
    }

    playSources = playSources.map(function (obj) {
        
        Object.keys(types).map(function (val) {
            if (obj.file.indexOf(val) != -1) {
                obj.type = types[val];
            }
        });

        if (obj.type != "") {
            return obj;
        }

    }).filter(function (obj) {
        return obj;
    });

    playerStartPosition = parseInt(GetQueryParameters(window.location.href)["MediaPosition"]);
    var conf = {
        techOrder: ["html5", "flash"]
    };
    if(videojs.browser.IS_EDGE || videojs.browser.IS_ANDROID){
        conf = {
            techOrder: ["html5", "flash"],
            html5: {
                nativeVideoTracks: false,
                nativeAudioTracks: false,
                hls: {
                    overrideNative: true,
                }
            }
        };
    }

    jwMediaPlayer = videojs("MediaPlayer1", conf);

    jwMediaPlayer.src({
        src: playSources[0].file,
        type: playSources[0].type
    });

    if (playSources[0].type == "video/mp4" && hasTranscript) {
        if (playSources[0].tracks.length > 0) {
            jwMediaPlayer.addRemoteTextTrack(
                 {
                     "default": true, // note the quotes around "default"!
                     kind: "subtitles",
                     srclang: "en",
                     label: playSources[0].tracks[0].label,
                     src: playSources[0].tracks[0].file
                 }
            )
        }
    }
    
    jwMediaPlayer.ready(function () {
        if (playerStartPosition > 0) {
            jwMediaPlayer.currentTime(playerStartPosition);
        }
        if (playSources[0].type == "application/x-mpegURL" && enableDVR) {
            jwMediaPlayer.dvrseekbar();
        }
        jwMediaPlayer.play();
    });    
}

function IsWowzaStream(playSources) {
    if (playSources == null) return false;
    if (playSources.length <= 0) return false;

    var ret = false;
    try {
        var i;
        for (i = 0; i < playSources.length; i++) {
            if (playSources[i].file.indexOf(".stream") > -1) ret = true;
        }
    } catch (e) {

    }

    return ret;

}

function IsJWSourceLive(playSources) {
    if (playSources == null) return false;
    if (playSources.length <= 0) return false;

    var ret = false;
    try {
        var i;
        for (i = 0; i < playSources.length; i++) {
            if (playSources[i].file.indexOf("(format=m3u8-aapl).m3u8") > -1) ret = true;
            if (playSources[i].file.indexOf(".stream") > -1) ret = true;
        }
    } catch (e) {

    }

    return ret;
}

function JWPlayerSetPosition(player, position) {
    jwMediaPlayer.currentTime(position);

    return true;
}

function SetPosition(position) {
    jwMediaPlayer.currentTime(position);

    return true;
}

function FixVideoSizeJW() {
    if (typeof (FixVideoSize) != "function") {
        return;
    }
    FixVideoSize(0, 0);
    //run again after a delay, in chrome the size won't take right away and I'm not sure why
    setTimeout(function () { FixVideoSize(0, 0); }, 100);
}

function TrySetBestQuality(player) {
    // if source is live - possible that quality is currently not set - try set it after timeout.
    if (player.getCurrentQuality() === -1) {
        setTimeout(function () { TrySetBestQuality(player); }, 200);
        return;
    }
    if (player.getCurrentQuality() !== 0) {
        return;
    }
    var allQualities = player.getQualityLevels();
    var bestQualityIndex = 0;
    var bestQuality = 0;
    for (var i = 0; i <= allQualities.length - 1; i++) {
        var quality = parseInt(allQualities[i].label);
        if (quality > bestQuality) {
            bestQuality = quality;
            bestQualityIndex = i;
        }
    };
    player.setCurrentQuality(bestQualityIndex);
}

// Dummy functions to prevent error by calling Silverlight JS.
function ChangeVideoPannelVisibility(isVisible) { }

function RememberPlayerPosition() { }

function RestorePlayerPosition() { }

function VideoScreenInitPlayer() { }



function ReportToWoopra(obj) {
    try {
        if (obj) {
            woopra.config({
                domain: "iqm2.com",
                cookie_name: "accelaTracker"
            });
            woopra.track("jw_buffer",
                Object.assign({
                    domain: window.location.hostname,
                    title: document.title,
                    note: "jwPlayer"
                },
                    obj));
        }
    } catch (err) {
        console.log("woopra log error! " + err);
    }
}