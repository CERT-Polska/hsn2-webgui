function(doc) {
	// usage example: http://host/hsn/_design/file_all_files/_view/view?group=true
    if( doc.type == "file" ) {
        emit(doc.job, 1);
    } 
}