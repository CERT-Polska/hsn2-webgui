function(doc) {
	// usage example: http://host/hsn/_design/url_summary_of_url_tree/_view/view?key=[3,"100"]
    if(doc.type == "url") {

		var url = doc.url_original.substr();

		emit(
				[doc.top_ancestor, doc.job], 
				{ 
					classification: doc.classification,
					url: url,
					id: doc._id,
					origin: doc.origin
				}
			);
    } 
}