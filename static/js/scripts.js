    var artistView = true;

		function toggleStatsView() {
		    artistView = !artistView;

		    var statsArtistView = document.getElementById("stats-artist-view");
		    var statsChronoView = document.getElementById("stats-chrono-view");

		    var viewTypeSwitch = document.getElementById("view-type-switch");

		    var viewInfoTopArtists = document.getElementById("view-info-top-artists");
		    var viewInfoAllScrobbles = document.getElementById("view-info-all-scrobbles");

		    if (artistView == true){
		        statsArtistView.style.display = "block";
		        statsChronoView.style.display = "none";

		        viewInfoTopArtists.style.display = "block";
		        viewInfoAllScrobbles.style.display = "none";

		        viewTypeSwitch.innerHTML = "<u>See All Scrobbles</u>"
		    } else {
		        statsArtistView.style.display = "none";
		        statsChronoView.style.display = "block";

                viewInfoTopArtists.style.display = "none";
		        viewInfoAllScrobbles.style.display = "block";

		        viewTypeSwitch.innerHTML = "<u>See Top Artists</u>"
		    }
        }

        function loadingButton(btn_id, url=null, loading_msg=null) {
           btn = document.getElementById(btn_id);
           if (loading_msg != null){
            btn.innerHTML = loading_msg;
           };
           btn.disabled = true;
           if (url != null){
            window.open(url,"_self")
           };
         };

        function formLoadingButton(btn_id, form_id, field_id, loading_msg="Please wait...") {
           field = document.getElementById(field_id);
           btn = document.getElementById(btn_id);
           if (field.value != ""){
               btn.value = loading_msg;
               btn.disabled = true;
               return true;
           }
           else{
             return false;
           };
         };

var showInfoText = false;

 function toggleInfoDisplay(){
    showInfoText = !showInfoText;

    var whatIs = document.getElementById("what-is-lasthop");
    var infoText = document.getElementById("info-text");

    if (showInfoText == true){
        infoText.style.display = "block";
        whatIs.style.display = "none";
    } else {
        infoText.style.display = "none";
        whatIs.style.display = "block";
    }

 };


var showPlaylistOptions = false;

 function togglePlaylistOptions(){
    showPlaylistOptions = !showPlaylistOptions;

    var btn = document.getElementById("make-playlist-btn");
    var options = document.getElementById("playlist-options");

    if (showPlaylistOptions == true){
        options.style.display = "block";
        btn.style.display = "none";
    } else {
        options.style.display = "none";
        btn.style.display = "block";
    }

 };

 function closePlaylistInfoBox(){
    var playlistInfoBox = document.getElementById("created-playlist-info");
    var makePlaylistBox = document.getElementById("make-playlist-box");

    playlistInfoBox.style.display = "none";
    makePlaylistBox.style.display = "block";

 };

 var showMorePlaylistOptions = false;

 function toggleMorePlaylistOptions(){
    var morePlaylistOptions = document.getElementById("more-playlist-options");

    showMorePlaylistOptions = !showMorePlaylistOptions;
    if (showMorePlaylistOptions == true){
     console.log(showMorePlaylistOptions);
        morePlaylistOptions.style.display = "block";
    } else {
        morePlaylistOptions.style.display = "none";
    }

 };

  var skipRecentlyPlayed = false;

  function toggleSkipRecentlyPlayed(){
    var skipRecentlyPlayedOptions = document.getElementById("skip-recent-options");

    skipRecentlyPlayed = !skipRecentlyPlayed;
    if (skipRecentlyPlayed == true){
        skipRecentlyPlayedOptions.style.display = "block";
    } else {
        skipRecentlyPlayedOptions.style.display = "none";
    }
 };

