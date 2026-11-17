;

function CDSCommon() {  }

/*

*/
/*
CDSCommon.fireEvent
var evt;
if(document.createEvent){
  evt = document.createEvent("HTMLEvents");
  evt.initEvent("dataavailable", true, true);
  evt.eventName = "dataavailable";
  element.dispatchEvent(evt);
} else {
  evt = document.createEventObject();
  evt.eventName = "dataavailable";
  evt.eventType = "dataavailable";
  element.fireEvent("on" + evt.eventType, evt);
}
*/

/*

*/
CDSCommon.fireEvent = function(eventName, eventData) {
  // // Add an event listener
  // document.addEventListener("name-of-event", function(e) {
  //   console.log(e.detail); // Prints "Example of an event"
  // });

  // Create the event
  var evt = new CustomEvent(eventName, {detail: eventData});

  //console.log('fireEvent, new evt:', evt);

  // Dispatch/Trigger/Fire the event
  document.dispatchEvent(evt);
}

/*

*/
CDSCommon.getCustomerAccessIDFromURL = function(){
	var parser = document.createElement('a');
	parser.href = location.href;
	var pathname = parser.pathname;
	if(pathname.indexOf('/') !== 0)
		pathname = '/' + pathname;
	//var path = parser.pathname.substring(1);
	var path = pathname.substring(1);
	var paths = path.split('/');
	var caID = paths[0];

	return caID;
}

/*

*/
CDSCommon.createCustomCSSLink = function(url){
	var link = document.createElement('link');
	link.rel = 'stylesheet';
	link.href = url;

	return link;
}

/*

*/
CDSCommon.isScrolledIntoView = function(elem, visibleAmount){  //visibleAmount is ALL, HALF, ONE (eg one px showing, or integer pixels (or undefined)
    var docViewTop = $(window).scrollTop();
    var docViewBottom = docViewTop + $(window).height();

    var elemTop = $(elem).offset().top;
    var elemBottom = elemTop + $(elem).height();

    //console.log('docViewTop: ' + docViewTop + ' elemTop: ' + elemTop + ' elemBottom: ' + elemBottom, ' docViewBottom: ' + docViewBottom);
		//console.log('typeof(visibleAmount) ', typeof(visibleAmount));
    
    //if(typeof(visibleAmount) == 'undefined')
    //	return ((elemBottom <= docViewBottom) && (elemTop >= docViewTop));
    

    if(typeof(visibleAmount) == 'string'){
    	if(visibleAmount == 'HALF'){
    		var visiblePXNeed = ((elemBottom - elemTop)/2);
    		var visibleBottom = elemTop + visiblePXNeed;
    		return !(docViewTop > visibleBottom);
    	}
	    else if(visibleAmount == 'ALL'){
	    	return ((elemBottom <= docViewBottom) && (elemTop >= docViewTop));	
	    }
	    else{
	    	return (elemBottom > docViewTop);
	    }
    }
    else if(typeof(visibleAmount) == 'number'){
    	var totalVisible = (elemBottom - elemTop);
			var visiblePXNeed = Math.min(totalVisible, Math.abs(visibleAmount));
    	var visibleBottom = elemBottom - visiblePXNeed;
			console.log('visiblePXNeed', visiblePXNeed, 'totalVisible', totalVisible, 'elemBottom', elemBottom, 'visibleBottom', visibleBottom)
    	return (visibleBottom > docViewTop);
    }
    else{
    	return (elemBottom > docViewTop);
    }
}

var PROTOCOL = window.location.protocol;
var HOST = window.location.host;
var hosts = HOST.split('.');
//if(hosts[0].indexOf('dev') > -1)
//{
	HOST = hosts[0] + 'api.' + hosts[1] + '.' + hosts[2];
//}
var CUSTOMER_ACCESS_ID = CDSCommon.getCustomerAccessIDFromURL();


