BUNDLE = VerticalGlyphProperties.glyphsPalette

.PHONY: all
all: $(BUNDLE)/Contents/_CodeSignature/CodeResources

.PHONY: $(BUNDLE)
$(BUNDLE): $(BUNDLE)/Contents/_CodeSignature/CodeResources

SRC := $(shell find $(BUNDLE) -name '*.py')
$(BUNDLE)/Contents/_CodeSignature/CodeResources: $(SRC)
	find $(BUNDLE) -name '*.pyc' -type f -exec rm '{}' \;
	command -v postbuild-codesign $(BUNDLE) >/dev/null 2>&1 && postbuild-codesign $(BUNDLE) 
	command -v postbuild-notarize $(BUNDLE) >/dev/null 2>&1 && postbuild-notarize $(BUNDLE)

.PHONY: clean
clean: 
	rm -rf $(BUNDLE)/Contents/_CodeSignature
	
.PHONY: install
install: 
	[ -L "$(HOME)/Library/Application Support/Glyphs/Plugins/$(BUNDLE)" ] && rm "$(HOME)/Library/Application Support/Glyphs/Plugins/$(BUNDLE)" || true
	ln -s "$(shell pwd)/$(BUNDLE)" "$(HOME)/Library/Application Support/Glyphs/Plugins/$(BUNDLE)"

.PHONY: test
test:
	python -m unittest discover tests
