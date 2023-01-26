# encoding: utf-8

from __future__ import division, print_function, unicode_literals
import objc
import traceback

from Foundation import NSArray, NSNotFound
from AppKit import NSColor, NSFont, NSFontFeatureSettingsAttribute, NSFontFeatureTypeIdentifierKey, NSFontFeatureSelectorIdentifierKey
from GlyphsApp import *
from GlyphsApp.plugins import *

# - Custom Column Implementation

from Foundation import NSSortDescriptor, NSString, NSValueTransformer
from AppKit import NSTableColumn, NSValueBinding, NSMenuItem, NSValueTransformerBindingOption

class VGPPDoubleToStringTransformer(NSValueTransformer):

    @classmethod
    def transformedValueClass(cls):
        return NSString

    @classmethod
    def allowsReverseTransformation(cls):
        return False

    def transformedValue_(self, value):
        double_value = value.doubleValue()
        if double_value > -1000000 and double_value < 1000000:
            return '{0:.0f}'.format(double_value)
        return ''

def is_table_column_visible(identifier):
    value = Glyphs.defaults["FontViewListColumnVisibe_{0}".format(identifier)]
    if value:
        return True
    return False

def insert_new_column(font, title, key_path, identifier=None, base_identifier='Name', compare_selector=None, value_transformer_class=None, insert_before_identifier=None, insert_after_identifier=None):

    identifier = identifier or title
    controller = font.fontView
    table_view = controller.listViewTableview()

    if not table_view.tableColumnWithIdentifier_(identifier):
        array_controller = controller.glyphsArrayController()
        new_column = NSTableColumn.alloc().initWithIdentifier_(identifier)
        new_column.setTitle_(title)
        new_column.setHidden_(not is_table_column_visible(identifier))
        if base_identifier:
            base_column = table_view.tableColumnWithIdentifier_(base_identifier)
            new_column.dataCell().setFont_(base_column.dataCell().font())
            new_column.setWidth_(base_column.width())
            new_column.setMinWidth_(base_column.minWidth())
            new_column.setMaxWidth_(base_column.maxWidth())
            compare_selector = compare_selector or (base_column.sortDescriptorPrototype() and base_column.sortDescriptorPrototype().selector())
        compare_selector = compare_selector or 'compare:'
        new_column.setSortDescriptorPrototype_(NSSortDescriptor.sortDescriptorWithKey_ascending_selector_(key_path, True, compare_selector))
        binding_option = None
        if value_transformer_class:
            binding_option = {NSValueTransformerBindingOption: value_transformer_class.alloc().init()}
        new_column.bind_toObject_withKeyPath_options_(NSValueBinding, array_controller, "arrangedObjects.{0}".format(key_path), binding_option)
        table_view.addTableColumn_(new_column)
        new_column_index = None
        if insert_before_identifier:
            new_column_index = table_view.columnWithIdentifier_(insert_before_identifier)
            new_column_index = new_column_index if new_column_index >= 0 else None
        if insert_after_identifier:
            new_column_index = table_view.columnWithIdentifier_(insert_after_identifier)
            new_column_index = new_column_index + 1 if new_column_index >= 0 else None
        if new_column_index is not None:
            table_view.moveColumn_toColumn_(table_view.numberOfColumns() - 1, new_column_index)

    menu = table_view.headerView().menu()
    if not menu.itemWithTitle_(title):
        base_menu_item = menu.itemArray()[-1]
        if base_identifier:
            base_menu_item = menu.itemWithTitle_(table_view.tableColumnWithIdentifier_(base_identifier).title())
        if base_menu_item:
            new_column = table_view.tableColumnWithIdentifier_(identifier)
            menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, '')
            menu_item.setTarget_(base_menu_item.target())
            menu_item.setAction_(base_menu_item.action())
            menu_item.setRepresentedObject_(new_column)
            new_index = menu.numberOfItems()
            if insert_before_identifier:
                base_column = table_view.tableColumnWithIdentifier_(insert_before_identifier)
                for i, item in enumerate(menu.itemArray()):
                    if item.representedObject() == base_column:
                        new_index = i
            if insert_after_identifier:
                base_column = table_view.tableColumnWithIdentifier_(insert_after_identifier)
                for i, item in enumerate(menu.itemArray()):
                    if item.representedObject() == base_column:
                        new_index = i + 1
            menu.insertItem_atIndex_(menu_item, new_index)

def customize_table_view_in_font(font):
    insert_new_column(font, 'Bottom Group',    'bottomKerningGroup', base_identifier='Right Group',    insert_after_identifier='Right Group')
    insert_new_column(font, 'Top Group',       'topKerningGroup',    base_identifier='Left Group',     insert_after_identifier='Right Group')
    insert_new_column(font, 'Vertical Origin', 'layer0.vertOrigin',  base_identifier='VerticalWidth',  insert_before_identifier='VerticalWidth', value_transformer_class=VGPPDoubleToStringTransformer)

# - Palette Implementation

def get_selected_layers_from_font(font):
    # Obtain currently selected layers in most situations, and wrap them with the proxy object.
    if font.currentTab:
        if len(font.selectedLayers) > 0:
            return VGPPLayer.layersFromArray_(font.selectedLayers)
    if font.selection:
        master = font.selectedFontMaster
        glyphs = sorted(set((e for e in font.selection if isinstance(e, GSGlyph))), key=lambda g: font.indexOfGlyph_(g))
        return VGPPLayer.layersFromArray_((glyph.layers[master.id] for glyph in glyphs))
    return tuple()

def get_glyphs_from_layers(layers):
    return tuple((t[0] for t in sorted(set(((layer.parent, layer.parent.parent.indexOfGlyph_(layer.parent)) for layer in layers)), key=lambda t: t[1])))

def is_placeholder_for_metrics_key_tag_in_layer(layer, tag):
    # FIXME: - [GSLayer vertWidthMetricsKeyState] doesn't seems to set the GSMetricsKeysPlaceholder bit.
    key = layer.plainMetricsKeyUI_(tag)
    return layer.metricsValue_atHeight_(tag, 0x7fffffffffffffff) < 0.0;

class VGPPLayer(NSObject):

    # A proxy/adapter object to GSLayer, which makes it Cocoa Binding ready.
    # Properties for building an UI for vertical glyph metrics look missing somehow and are not on par with the horizontal one.

    # Never tried 'depends_on' of PyObjC though, I suppose it would synthesise + keyPathsForValuesAffecting<Key> methods.
    layer                       = objc.object_property(depends_on=['topMetricsKeyUI', 'bottomMetricsKeyUI', 'vertOriginUI', 'vertWidthMetricsKeyUI'])
    topMetricsKeyUI             = objc.object_property(ivar=None, depends_on=['topMetricsKeyIsInSync'])
    bottomMetricsKeyUI          = objc.object_property(ivar=None, depends_on=['bottomMetricsKeyIsInSync'])
    vertOriginUI                = objc.object_property(ivar=None)
    vertWidthMetricsKeyUI       = objc.object_property(ivar=None, depends_on=['vertWidthMetricsKeyIsInSync'])
    topMetricsKeyIsInSync       = objc.object_property(ivar=None, read_only=True, typestr=objc._C_BOOL, depends_on=['topMetricsKeyColor'])
    bottomMetricsKeyIsInSync    = objc.object_property(ivar=None, read_only=True, typestr=objc._C_BOOL, depends_on=['bottomMetricsKeyColor'])
    vertWidthMetricsKeyIsInSync = objc.object_property(ivar=None, read_only=True, typestr=objc._C_BOOL, depends_on=['vertWidthMetricsKeyColor'])
    topMetricsKeyColor          = objc.object_property(ivar=None, read_only=True, typestr=objc._C_ID)
    bottomMetricsKeyColor       = objc.object_property(ivar=None, read_only=True, typestr=objc._C_ID)
    vertOriginColor             = objc.object_property(ivar=None, read_only=True, typestr=objc._C_ID)
    vertWidthMetricsKeyColor    = objc.object_property(ivar=None, read_only=True, typestr=objc._C_ID)

    has_registered_metadata = False
    @classmethod
    def registerMetadata(cls):
        # Register metadata to PyObjC so that the byref pointer passing won't crash the process.
        if not cls.has_registered_metadata:
            for selector_name in (b'vertWidthMetricsKeyUIisPlaceholder:', b'vertOriginUIisPlaceholder:'):
                objc.registerMetaDataForSelector(
                    b'GSLayer',
                    selector_name,
                    {
                        'arguments': {
                            2: {'null_accepted': False, 'type_modifier': objc._C_OUT, 'type': objc._C_PTR + objc._C_CHR},
                        },
                        'retval': {
                            'type': objc._C_ID
                        }
                    }
                )
            cls.has_registered_metadata = True

    @classmethod
    def layersFromArray_(cls, array):
        return NSArray.arrayWithArray_([cls.alloc().initWithLayer_(layer) for layer in array])

    @property
    def parent(self):
        return self.layer.parent

    def initWithLayer_(self, layer):
        self = objc.super(VGPPLayer, self).init()
        if self is None: return None
        VGPPLayer.registerMetadata()
        self.layer = layer
        return self

    def __del__(self):
        # Make sure to stop observing changes before deallocation.
        self.layer = None

    def __hash__(self):
        return self.layer.hash()

    def __eq__(self, obj):
        if isinstance(obj, VGPPLayer):
            return self.layer == obj.layer
        return False

    def observeValueForKeyPath_ofObject_change_context_(self, key_path, object, change, context):
        # Call - didChangeValueForKey: to notify changes to the palette.
        translated_key_path = {
            'topMetricsKeyUI':       'topMetricsKeyUI',
            'bottomMetricsKeyUI':    'bottomMetricsKeyUI',
            'vertOrigin':            'vertOriginUI',
            'vertWidthMetricsKeyUI': 'vertWidthMetricsKeyUI'
        }.get(key_path)
        if translated_key_path:
            self.didChangeValueForKey_(translated_key_path)

    @layer.setter
    def layer(self, value):
        # Observe changes outside this palette with KVO.
        key_paths = ('topMetricsKeyUI', 'bottomMetricsKeyUI', 'vertOrigin', 'vertWidthMetricsKeyUI')
        if self._layer:
            for key_path in key_paths:
                self._layer.removeObserver_forKeyPath_(self, key_path)
        self._layer = value
        if value:
            for key_path in key_paths:
                self._layer.addObserver_forKeyPath_options_context_(self, key_path, 0, None)

    @topMetricsKeyUI.getter
    def topMetricsKeyUI(self):
        return self.layer.pyobjc_instanceMethods.topMetricsKeyUI()

    @bottomMetricsKeyUI.getter
    def bottomMetricsKeyUI(self):
        return self.layer.pyobjc_instanceMethods.bottomMetricsKeyUI()

    @vertOriginUI.getter
    def vertOriginUI(self):
        is_placeholder = False
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertOriginUIisPlaceholder:'):
            _, is_placeholder = self.layer.pyobjc_instanceMethods.vertOriginUIisPlaceholder_(None)
        if is_placeholder: return None
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertOriginKeyUI'):
            return self.layer.pyobjc_instanceMethods.vertOriginKeyUI() if -1000000 < self.layer.pyobjc_instanceMethods.vertOrigin() < 1000000 else None
        return "{0:.0f}".format(self.layer.pyobjc_instanceMethods.vertOrigin()) if -1000000 < self.layer.pyobjc_instanceMethods.vertOrigin() < 1000000 else None

    @vertWidthMetricsKeyUI.getter
    def vertWidthMetricsKeyUI(self):
        # Return nil to prefer the placeholder string set in XIB for simplicity.
        is_placeholder = False
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyState'):
            is_placeholder = self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyState() & (1 << 2)
            if not is_placeholder:
                is_placeholder = is_placeholder_for_metrics_key_tag_in_layer(self.layer, 0x4)
        elif self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyUIisPlaceholder:'):
            _, is_placeholder = self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyUIisPlaceholder_(None)
        return self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyUI() if not is_placeholder else None

    @topMetricsKeyUI.setter
    def topMetricsKeyUI(self, value):
        self.layer.pyobjc_instanceMethods.setTopMetricsKeyUI_(value)

    @bottomMetricsKeyUI.setter
    def bottomMetricsKeyUI(self, value):
        self.layer.pyobjc_instanceMethods.setBottomMetricsKeyUI_(value)

    @vertOriginUI.setter
    def vertOriginUI(self, value):
        if value is not None:
            self.layer.pyobjc_instanceMethods.setVertOriginUI_(value)
        else:
            # Apart from the metrics key, make sure to reset to the default value as well.
            self.layer.pyobjc_instanceMethods.setVertOriginUI_('')
            self.layer.pyobjc_instanceMethods.setVertOrigin_(NSNotFound)

    @vertWidthMetricsKeyUI.setter
    def vertWidthMetricsKeyUI(self, value):
        if value is not None:
            self.layer.pyobjc_instanceMethods.setVertWidthMetricsKeyUI_(value)
        else:
            # Apart from the metrics key, make sure to reset to the default value as well.
            self.layer.pyobjc_instanceMethods.setVertWidthMetricsKeyUI_('')
            self.layer.pyobjc_instanceMethods.setVertWidth_(NSNotFound)

    @topMetricsKeyUI.validate
    def topMetricsKeyUI(self, value, error):
        return self.layer.validateLeftetricsKey_error_(value, None)

    @bottomMetricsKeyUI.validate
    def bottomMetricsKeyUI(self, value, error):
        return self.layer.validateRightMetricsKey_error_(value, None)

    @vertOriginUI.validate
    def vertOriginUI(self, value, error):
        try:
            _ = float(value)
        except ValueError:
            return (False, None, None)
        return (True, value, None)

    @vertWidthMetricsKeyUI.validate
    def vertWidthMetricsKeyUI(self, value, error):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyUI'):
            return self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyUI()
        return self.layer.validateVertWidthMetricsKey_error_(value, None)

    @topMetricsKeyIsInSync.getter
    def topMetricsKeyIsInSync(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('leftMetricsKeyState'):
            return not (self.layer.pyobjc_instanceMethods.leftMetricsKeyState() & (1 << 0))
        elif self.layer.pyobjc_instanceMethods.topMetricsKey():
            duplicated = self.layer.copy()
            duplicated.syncTopMetrics()
            return self.layer.pyobjc_instanceMethods.TSB() == duplicated.pyobjc_instanceMethods.TSB()
        return True

    @bottomMetricsKeyIsInSync.getter
    def bottomMetricsKeyIsInSync(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('bottomMetricsKeyState'):
            return not (self.layer.pyobjc_instanceMethods.bottomMetricsKeyState() & (1 << 0))
        elif self.layer.pyobjc_instanceMethods.bottomMetricsKey():
            duplicated = self.layer.copy()
            duplicated.syncBottomMetrics()
            return self.layer.pyobjc_instanceMethods.BSB() == duplicated.pyobjc_instanceMethods.BSB()
        return True

    @vertWidthMetricsKeyIsInSync.getter
    def vertWidthMetricsKeyIsInSync(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyState'):
            return not (self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyState() & (1 << 0))
        elif self.layer.pyobjc_instanceMethods.respondsToSelector_('syncVertWidthMetrics'):
            duplicated = self.layer.copy()
            duplicated.syncVertWidthMetrics()
            return self.layer.pyobjc_instanceMethods.vertWidth() == duplicated.pyobjc_instanceMethods.vertWidth()
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyIsInSync'):
            return self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyIsInSync()
        return True

    @topMetricsKeyColor.getter
    def topMetricsKeyColor(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('colorForMetricsState:') and self.layer.pyobjc_instanceMethods.respondsToSelector_('topMetricsKeyState'):
            return self.layer.pyobjc_instanceMethods.colorForMetricsState_(self.layer.pyobjc_instanceMethods.topMetricsKeyState())
        return NSColor.controlTextColor() if self.topMetricsKeyIsInSync else NSColor.systemRedColor()

    @bottomMetricsKeyColor.getter
    def bottomMetricsKeyColor(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('colorForMetricsState:') and self.layer.pyobjc_instanceMethods.respondsToSelector_('bottomMetricsKeyState'):
            return self.layer.pyobjc_instanceMethods.colorForMetricsState_(self.layer.pyobjc_instanceMethods.bottomMetricsKeyState())
        return NSColor.controlTextColor() if self.bottomMetricsKeyIsInSync else NSColor.systemRedColor()

    @vertOriginColor.getter
    def vertOriginColor(self):
        return NSColor.controlTextColor()

    @vertWidthMetricsKeyColor.getter
    def vertWidthMetricsKeyColor(self):
        if self.layer.pyobjc_instanceMethods.respondsToSelector_('colorForMetricsState:') and self.layer.pyobjc_instanceMethods.respondsToSelector_('vertWidthMetricsKeyState'):
            return self.layer.pyobjc_instanceMethods.colorForMetricsState_(self.layer.pyobjc_instanceMethods.vertWidthMetricsKeyState())
        return NSColor.controlTextColor() if self.vertWidthMetricsKeyIsInSync else NSColor.systemRedColor()

class VerticalGlyphPropertiesPalette(PalettePlugin):

    dialog = objc.IBOutlet()

    # Cocoa Binding and NSArrayController will do 99% of the job. See also IBdialog.xib.
    selectedGlyphsArrayController = objc.IBOutlet()
    selectedLayersArrayController = objc.IBOutlet()

    topMetricsKeyTextField       = objc.IBOutlet()
    bottomMetricsKeyTextField    = objc.IBOutlet()
    vertOriginTextField          = objc.IBOutlet()
    vertWidthMetricsKeyTextField = objc.IBOutlet()
    topKerningGroupTextField     = objc.IBOutlet()
    bottomKerningGroupTextField  = objc.IBOutlet()

    # Seems that making it BOOL makes the NSButton binding handy.
    enabled        = objc.object_property(typestr=objc._C_BOOL)
    editable       = objc.object_property(typestr=objc._C_BOOL)
    selectedGlyphs = objc.object_property()
    selectedLayers = objc.object_property()

    hasAddedCustomColumns = objc.object_property(typestr=objc._C_BOOL)

    @objc.python_method
    @staticmethod
    def make_slashed_zero_nsfont(nsfont):
        # Activate the same AAT feature as Glyphs to get the slashed zero effect.
        kStylisticAlternativesType = 35
        kStylisticAltSixOnSelector = 12
        descriptor = nsfont.fontDescriptor().fontDescriptorByAddingAttributes_({NSFontFeatureSettingsAttribute: [{
            NSFontFeatureTypeIdentifierKey:     kStylisticAlternativesType,
            NSFontFeatureSelectorIdentifierKey: kStylisticAltSixOnSelector
        }]})
        return NSFont.fontWithDescriptor_size_(descriptor, nsfont.pointSize())

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({'en': 'Vertical Properties'})
        self.enabled  = False
        self.editable = False
        self.selectedGlyphs = []
        self.selectedLayers = []
        self.hasAddedCustomColumns = False
        self.loadNib('IBdialog', __file__)
        # Enable keyboard navigation with the Tab key.
        self.topMetricsKeyTextField.setNextKeyView_(self.bottomMetricsKeyTextField)
        self.bottomMetricsKeyTextField.setNextKeyView_(self.vertOriginTextField)
        self.vertOriginTextField.setNextKeyView_(self.vertWidthMetricsKeyTextField)
        self.vertWidthMetricsKeyTextField.setNextKeyView_(self.topKerningGroupTextField)
        self.topKerningGroupTextField.setNextKeyView_(self.bottomKerningGroupTextField)
        self.bottomKerningGroupTextField.setNextKeyView_(self.topMetricsKeyTextField)
        # Apply the same font style with Glyphs to the text fields.
        self.topMetricsKeyTextField.setFont_(self.make_slashed_zero_nsfont(self.topMetricsKeyTextField.font()))
        self.bottomMetricsKeyTextField.setFont_(self.make_slashed_zero_nsfont(self.bottomMetricsKeyTextField.font()))
        self.vertOriginTextField.setFont_(self.make_slashed_zero_nsfont(self.vertOriginTextField.font()))
        self.vertWidthMetricsKeyTextField.setFont_(self.make_slashed_zero_nsfont(self.vertWidthMetricsKeyTextField.font()))
        self.topKerningGroupTextField.setFont_(self.make_slashed_zero_nsfont(self.topKerningGroupTextField.font()))
        self.bottomKerningGroupTextField.setFont_(self.make_slashed_zero_nsfont(self.bottomKerningGroupTextField.font()))

    @objc.python_method
    def start(self):
        Glyphs.addCallback(self.update, UPDATEINTERFACE)

    @objc.python_method
    def __del__(self):
        Glyphs.removeCallback(self.update)

    @objc.python_method
    def update(self, sender):
        try:
            selected_layers = None
            if self.windowController():
                if isinstance(sender.object(), (objc.lookUpClass('GSEditViewController'), objc.lookUpClass('GSFontViewController'))):
                    selected_layers = VGPPLayer.layersFromArray_(sender.object().selectedLayers or [])
                else:
                    font = sender.object()
                    selected_layers = get_selected_layers_from_font(font)
                    if not self.hasAddedCustomColumns:
                        customize_table_view_in_font(font)
                        self.hasAddedCustomColumns = True
            if selected_layers and len(selected_layers) > 0:
                # Update the binding only when the selection is changed to prevent the possible perfomance degradation.
                if self.selectedLayers != selected_layers:
                    # Since the text field value are binded with - [NSArrayController selection] in XIB, make sure to select all the items available.
                    selected_glyphs = get_glyphs_from_layers(selected_layers)
                    self.selectedLayers = selected_layers
                    self.selectedGlyphs = selected_glyphs
                    self.selectedLayersArrayController.addSelectedObjects_(self.selectedLayersArrayController.arrangedObjects())
                    self.selectedGlyphsArrayController.addSelectedObjects_(self.selectedGlyphsArrayController.arrangedObjects())
                    self.enabled = True
            else:
                self.selectedLayers = []
                self.selectedGlyphs = []
                self.enabled = False
        except:
            LogError(traceback.format_exc())

    @objc.python_method
    def __file__(self):
        """Please leave this method unchanged"""
        return __file__

    def sortID(self):
        return 0
