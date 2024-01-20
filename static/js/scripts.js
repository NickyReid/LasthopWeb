    var artistView = true;

		function toggleStatsView() {
		    artistView = !artistView;

		    var statsArtistView = document.getElementById("stats-artist-view");
		    var statsChronoView = document.getElementById("stats-chrono-view");

		    if (artistView == true){
		        statsArtistView.style.display = "block";
		        statsChronoView.style.display = "none";
		    } else {
		        statsArtistView.style.display = "none";
		        statsChronoView.style.display = "block";
		    }
        }

        function loadingButton(btn_id, url=null, loading_msg=null) {
           btn = document.getElementById(btn_id);
           if (loading_msg != null){
            btn.innerHTML = loading_msg;
           };
           btn.disabled = true;
           if (url){
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