function(doc) {
	// usage example: http://host/hsn/_design/file_summary/_view/view?key=[3,"100"]
    if(doc.type == "file") {

		emit(
				[doc.top_ancestor, doc.job], 
				{ 
					classification: doc.classification,
					id: doc._id,
					parent: doc.parent
				}
			);
    } 
}