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