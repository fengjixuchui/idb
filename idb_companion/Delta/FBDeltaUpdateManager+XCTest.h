/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#import <Foundation/Foundation.h>

#import <FBControlCore/FBControlCore.h>
#import <XCTestBootstrap/XCTestBootstrap.h>
#import "FBDeltaUpdateManager.h"
#import "FBIDBTestOperation.h"

NS_ASSUME_NONNULL_BEGIN

@class FBTemporaryDirectory;
@class FBXCTestBundleStorage;
@class TestRunInfo;

@class FBXCTestRunRequest;

/**
 An incremental update for a given session
 */
@interface FBXCTestDelta : NSObject

/**
 The Identifier of the Session
 */
@property (nonatomic, copy, readonly) NSString *identifier;

/**
 The Test Results
 */
@property (nonatomic, copy, readonly) NSArray<FBTestRunUpdate *> *results;

/**
 Any incremental logging output.
 */
@property (nonatomic, copy, readonly) NSString *logOutput;

/**
 The Result Bundle Path, if relevant.
 */
@property (nonatomic, copy, nullable, readonly) NSString *resultBundlePath;

/**
 The Execution State.
 */
@property (nonatomic, assign, readonly) FBIDBTestOperationState state;

/**
 The error to report if any.
 */
@property (nonatomic, assign, readonly) NSError *error;

@end

typedef FBDeltaUpdateManager<FBXCTestDelta *, FBIDBTestOperation *, FBXCTestRunRequest *> FBXCTestDeltaUpdateManager;

/**
 Manages running tests and returning partial results
 */
@interface FBDeltaUpdateManager (XCTest)

#pragma mark Initializers

/**
 A delta update manager for XCTest Execution.

 @param target the target to use.
 @param bundleStorage the bundle storage component to use.
 @param temporaryDirectory the temporary directory to use.
 @return a delta update manager for XCTest Execution.
 */
+ (FBXCTestDeltaUpdateManager *)xctestManagerWithTarget:(id<FBiOSTarget>)target bundleStorage:(FBXCTestBundleStorage *)bundleStorage temporaryDirectory:(FBTemporaryDirectory *)temporaryDirectory;

@end

NS_ASSUME_NONNULL_END
