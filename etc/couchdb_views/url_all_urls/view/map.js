function(doc) {
	// usage example: http://host/hsn/_design/url_all_urls/_view/view?group=true
    if( doc.type == "url" ) {
        emit(doc.job, 1);
    } 
}